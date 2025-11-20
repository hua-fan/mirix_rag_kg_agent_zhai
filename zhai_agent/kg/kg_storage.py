from neo4j import GraphDatabase, exceptions
from typing import List, Dict, Optional, Union
from datetime import datetime
import re
import logging
from ..config import settings

logger = logging.getLogger(__name__)

URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "huafan123")

# 定义合法的标签/关系类型格式（Neo4j要求：字母开头，可包含字母、数字、下划线）
VALID_LABEL_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')

class KGStorage:
    def __init__(self):
        """初始化Neo4j连接"""
        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_lifetime=3600  # 连接最大生命周期1小时
            )
            # 测试连接
            self.driver.verify_connectivity()
            logger.info("✅ Neo4j图库连接成功")
        except exceptions.Neo4jError as e:
            raise Exception(f"❌ Neo4j连接失败：{str(e)}")
        except exceptions.ServiceUnavailable as e:
            raise Exception(f"❌ Neo4j服务不可用：{str(e)}")
        except Exception as e:
            raise Exception(f"❌ 未知连接错误：{str(e)}")

    # 添加到 KGStorage 类中（建议放在 __init__ 之后）
    def _serialize_result(self, data):
        """递归处理Neo4j返回的数据，将时间对象转换为字符串"""
        if isinstance(data, list):
            return [self._serialize_result(item) for item in data]
        elif isinstance(data, dict):
            return {k: self._serialize_result(v) for k, v in data.items()}
        # 检查是否有 isoformat 方法 (涵盖 datetime, date, time, neo4j.time.DateTime)
        elif hasattr(data, 'isoformat'):
            return data.isoformat()
        else:
            return data

    def _validate_label(self, label: str) -> None:
        """验证标签/关系类型的合法性"""
        if not VALID_LABEL_PATTERN.match(label):
            raise ValueError(
                f"非法标签/关系类型：{label}。要求：字母开头，仅包含字母、数字、下划线"
            )

    def create_entity(
        self, 
        entity_name: str, 
        entity_type: str, 
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        创建实体节点（若已存在则更新属性）
        
        Args:
            entity_name: 实体名称（唯一标识）
            entity_type: 实体类型（节点标签）
            metadata: 实体属性字典
           
        Returns:
            创建/更新后的实体信息
        """
        if not entity_name or not isinstance(entity_name, str):
            raise ValueError("实体名称不能为空且必须是字符串")
        entity_type = entity_type.upper()
        self._validate_label(entity_type)
        
        metadata = metadata or {}
        # 过滤掉None值，避免Neo4j存储null
        metadata = {k: v for k, v in metadata.items() if v is not None}
        
        cypher = f"""
            MERGE (e:{entity_type} {{name: $name}})
            SET e += $metadata, 
                e.updated_at = datetime(),
                e.created_at = coalesce(e.created_at, datetime())
            RETURN e {{
                id: id(e),
                name: e.name,
                type: '{entity_type}',
                metadata: properties(e),  
                created_at: e.created_at,
                updated_at: e.updated_at
            }} AS entity
        """

        try:
            with self.driver.session() as session:
                result = session.run(cypher, name=entity_name, metadata=metadata).single()
                return self._serialize_result(result["entity"]) if result else None
        except exceptions.Neo4jError as e:
            raise Exception(f"❌ 创建实体失败：{str(e)}")

    def batch_create_entities(
        self, 
        entities: List[Dict[str, Union[str, Dict]]]
    ) -> List[Dict]:
        """
        批量创建实体节点
        
        Args:
            entities: 实体列表，每个实体包含：name, type, metadata(可选)
        
        Returns:
            批量创建/更新后的实体信息列表
        """
        if not isinstance(entities, list) or len(entities) == 0:
            raise ValueError("实体列表不能为空")
        
        results = []
        for entity in entities:
            try:
                entity_name = entity.get("name")
                entity_type = entity.get("type")
                metadata = entity.get("metadata", {})
                
                if not entity_name or not entity_type:
                    logger.warning(f"⚠️ 跳过无效实体：{entity}（缺少name或type）")
                    continue
                
                entity_type = entity_type.upper()
                result = self.create_entity(entity_name, entity_type, metadata)
                results.append(result)
            except Exception as e:
                logger.error(f"⚠️ 创建实体失败：{entity}，错误：{str(e)}")
                continue
        return results

    def search_entities(
        self, 
        keyword: str,
        entity_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        搜索实体（基于名称模糊匹配）
        
        Args:
            keyword: 搜索关键词（支持模糊匹配）
            entity_type: 实体类型（节点标签，可选）
            limit: 返回结果数量限制
        
        Returns:
            匹配的实体列表
        """
        if not keyword:
            return []
        
        params = {"keyword": keyword, "limit": limit}
        
        # 构建标签查询
        if entity_type:
            entity_type = entity_type.upper()
            self._validate_label(entity_type)
            label_clause = f":{entity_type}"
        else:
            label_clause = ""
        
        cypher = f"""
            MATCH (e{label_clause})
            WHERE toLower(e.name) CONTAINS toLower($keyword)
            RETURN e {{
                id: id(e),
                name: e.name,
                type: labels(e)[0],
                metadata: properties(e),
                created_at: toString(e.created_at),  // 转换为字符串
                updated_at: toString(e.updated_at)   // 转换为字符串
            }} AS entity
            LIMIT $limit
        """
        
        try:
            with self.driver.session() as session:
                results = session.run(cypher, **params)
                data = [record["entity"] for record in results if record["entity"]]
                return self._serialize_result(data)
        except exceptions.Neo4jError as e:
            raise Exception(f"❌ 搜索实体失败：{str(e)}")

    def get_entities_by_type(self, entity_type: str, limit: int = 100) -> List[Dict]:
        """
        获取指定类型的所有实体
        
        Args:
            entity_type: 实体类型（节点标签）
            limit: 返回结果数量限制
        
        Returns:
            实体列表
        """
        if not entity_type:
            raise ValueError("实体类型不能为空")
        
        entity_type = entity_type.upper()
        self._validate_label(entity_type)
        
        cypher = f"""
            MATCH (e{label_clause})
            WHERE toLower(e.name) CONTAINS toLower($keyword)
            RETURN e {{
                id: id(e),
                name: e.name,
                type: labels(e)[0],
                metadata: properties(e),
                created_at: toString(e.created_at),  // 转换为字符串
                updated_at: toString(e.updated_at)   // 转换为字符串
            }} AS entity
            LIMIT $limit
        """
        
        try:
            with self.driver.session() as session:
                results = session.run(cypher, limit=limit)
                # ✅ 修改这里
                data = [record["entity"] for record in results if record["entity"]]
                return self._serialize_result(data)
        except exceptions.Neo4jError as e:
            raise Exception(f"❌ 获取类型实体失败：{str(e)}")

    def get_entity(
        self, 
        entity_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        properties: Optional[Dict] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        查询实体节点（支持多条件组合查询）
        """
        properties = properties or {}
        where_clauses = []
        params = {}
        
        # 构建查询条件
        if entity_name:
            where_clauses.append("e.name = $name")
            params["name"] = entity_name
        
        # 构建属性查询条件
        for key, value in properties.items():
            if value is not None:
                where_clauses.append(f"e.{key} = ${key}")
                params[key] = value
        
        where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # 构建标签查询
        if entity_type:
            entity_type = entity_type.upper()
            self._validate_label(entity_type)
            label_clause = f":{entity_type}"
        else:
            label_clause = ""
        
        # 注意：这里的 Cypher 里的 toString 可以保留，也可以去掉，
        # 因为下面加上 _serialize_result 后都能兼容。
        cypher = f"""
            MATCH (e{label_clause})
            {where_str}
            RETURN e {{
                id: id(e),
                name: e.name,
                type: labels(e)[0],
                metadata: properties(e),
                created_at: e.created_at, 
                updated_at: e.updated_at
            }} AS entity
            LIMIT $limit
        """
        params["limit"] = limit
        
        try:
            with self.driver.session() as session:
                results = session.run(cypher, **params)
                data = [record["entity"] for record in results if record["entity"]]
                # ✅ 修复点 1: 加上序列化处理
                return self._serialize_result(data)
        except exceptions.Neo4jError as e:  # ✅ 修复点 2: 修正拼写错误 (原为 Neo4jNeo4jError)
            raise Exception(f"❌ 查询实体失败：{str(e)}")

    def update_entity(
        self,
        entity_name: str,
        entity_type: str,
        metadata: Dict,
        upsert: bool = False
    ) -> Optional[Dict]:
        """
        更新实体属性
        
        Args:
            entity_name: 实体名称（唯一标识）
            entity_type: 实体类型（节点标签）
            metadata: 要更新的属性字典
            upsert: 不存在时是否创建（默认不创建）
        
        Returns:
            更新后的实体信息（不存在且不创建时返回None）
        """
        if not entity_name or not entity_type:
            raise ValueError("实体名称和类型不能为空")
            
        entity_type = entity_type.upper()
        self._validate_label(entity_type)
        
        if not metadata:
            raise ValueError("更新属性不能为空")
        
        # 过滤掉None值
        metadata = {k: v for k, v in metadata.items() if v is not None}
        
        match_clause = "MERGE" if upsert else "MATCH"
        
        cypher = f"""
            {match_clause} (e:{entity_type} {{name: $name}})
            SET e += $metadata, e.updated_at = datetime()
            {"SET e.created_at = datetime()" if upsert else ""}
            RETURN e {{
                id: id(e),
                name: e.name,
                type: '{entity_type}',
                metadata: properties(e),
                created_at: toString(e.created_at),
                updated_at: toString(e.updated_at)
            }} AS entity
        """
        try:
            with self.driver.session() as session:
                result = session.run(cypher, name=entity_name, metadata=metadata).single()
                # ✅ 修改这里
                return self._serialize_result(result["entity"]) if result else None
        except exceptions.Neo4jError as e:
            raise Exception(f"❌ 更新实体失败：{str(e)}")

    def delete_entity(
        self,
        entity_name: str,
        entity_type: str,
        delete_relationships: bool = True
    ) -> bool:
        """
        删除实体节点
        
        Args:
            entity_name: 实体名称（唯一标识）
            entity_type: 实体类型（节点标签）
            delete_relationships: 是否同时删除关联的关系（默认删除）
        
        Returns:
            删除成功返回True，失败返回False
        """
        if not entity_name or not entity_type:
            raise ValueError("实体名称和类型不能为空")
            
        entity_type = entity_type.upper()
        self._validate_label(entity_type)
        
        if delete_relationships:
            # 先删除关系再删除节点
            cypher = f"""
                MATCH (e:{entity_type} {{name: $name}})-[r]-()
                DELETE r
                WITH e
                MATCH (e:{entity_type} {{name: $name}})
                DELETE e
                RETURN count(e) AS deleted_count
            """
        else:
            # 仅删除节点（如果有关联关系会失败）
            cypher = f"""
                MATCH (e:{entity_type} {{name: $name}})
                DELETE e
                RETURN count(e) AS deleted_count
            """
        
        try:
            with self.driver.session() as session:
                result = session.run(cypher, name=entity_name).single()
                return result["deleted_count"] > 0 if result else False
        except exceptions.Neo4jError as e:
            raise Exception(f"❌ 删除实体失败：{str(e)}")

    def create_relationship(
        self,
        subj_name: str,
        subj_type: str,
        rel_type: str,
        obj_name: str,
        obj_type: str,
        metadata: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        创建实体关系（主体和客体必须已存在）
        
        Args:
            subj_name: 主体实体名称
            subj_type: 主体实体类型
            rel_type: 关系类型
            obj_name: 客体实体名称
            obj_type: 客体实体类型
            metadata: 关系属性字典
        
        Returns:
            创建后的关系信息
        """
        # 参数验证
        for param, name in [(subj_name, "主体名称"), (subj_type, "主体类型"),
                           (rel_type, "关系类型"), (obj_name, "客体名称"),
                           (obj_type, "客体类型")]:
            if not param or not isinstance(param, str):
                raise ValueError(f"{name}不能为空且必须是字符串")
            
        subj_type = subj_type.upper()
        obj_type = obj_type.upper()
        rel_type = rel_type.upper()
        self._validate_label(subj_type)
        self._validate_label(obj_type)
        self._validate_label(rel_type)
        
        metadata = metadata or {}
        metadata = {k: v for k, v in metadata.items() if v is not None}
        
        cypher = f"""
            MATCH (s:{subj_type} {{name: $subj_name}}), (o:{obj_type} {{name: $obj_name}})
            MERGE (s)-[r:{rel_type}]->(o)
            SET r += $metadata,
                r.updated_at = datetime(),
                r.created_at = coalesce(r.created_at, datetime())
            RETURN r {{
                id: id(r),
                type: type(r),
                subject: {{name: s.name, type: '{subj_type}'}},
                object: {{name: o.name, type: '{obj_type}'}},
                metadata: properties(r) ,
                created_at: r.created_at,
                updated_at: r.updated_at
            }} AS relationship
        """
        try:
            with self.driver.session() as session:
                result = session.run(
                    cypher,
                    subj_name=subj_name,
                    obj_name=obj_name,
                    metadata=metadata
                ).single()
                if not result:
                    raise Exception(f"主体({subj_type}:{subj_name})或客体({obj_type}:{obj_name})不存在")
                # ✅ 修改这里
                return self._serialize_result(result["relationship"])
        except exceptions.Neo4jError as e:
            raise Exception(f"❌ 创建关系失败：{str(e)}")

    def batch_create_relationships(
        self,
        relationships: List[Dict[str, Union[str, Dict]]]
    ) -> List[Dict]:
        """
        批量创建关系
        
        Args:
            relationships: 关系列表，每个关系包含：
                subj_name, subj_type, rel_type, obj_name, obj_type, metadata(可选)
        
        Returns:
            批量创建后的关系信息列表
        """
        if not isinstance(relationships, list) or len(relationships) == 0:
            raise ValueError("关系列表不能为空")
        
        results = []
        for rel in relationships:
            try:
                required_fields = ["subj_name", "subj_type", "rel_type", "obj_name", "obj_type"]
                if not all(field in rel for field in required_fields):
                    logger.warning(f"⚠️ 跳过无效关系：{rel}（缺少必填字段）")
                    continue
                
                subj_type = rel["subj_type"].upper()
                obj_type = rel["obj_type"].upper()
                rel_type = rel["rel_type"].upper()

                result = self.create_relationship(
                    subj_name=rel["subj_name"],
                    subj_type=subj_type,
                    rel_type=rel_type,
                    obj_name=rel["obj_name"],
                    obj_type=obj_type,  
                    metadata=rel.get("metadata", {})
                )
                results.append(result)
            except Exception as e:
                logger.error(f"⚠️ 创建关系失败：{rel}，错误：{str(e)}")
                continue
        return results

    def get_relationships(
        self,
        subj_name: Optional[str] = None,
        subj_type: Optional[str] = None,
        rel_type: Optional[str] = None,
        obj_name: Optional[str] = None,
        obj_type: Optional[str] = None,
        metadata: Optional[Dict] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        查询关系（支持多条件组合查询）
        
        Args:
            subj_name: 主体名称
            subj_type: 主体类型
            rel_type: 关系类型
            obj_name: 客体名称
            obj_type: 客体类型
            metadata: 关系属性字典
            limit: 返回结果上限
        
        Returns:
            匹配的关系列表
        """
        metadata = metadata or {}
        where_clauses = []
        params = {}
        
        # 构建节点查询条件
        if subj_name:
            where_clauses.append("s.name = $subj_name")
            params["subj_name"] = subj_name
        
        if obj_name:
            where_clauses.append("o.name = $obj_name")
            params["obj_name"] = obj_name
        
        # 构建关系属性查询条件
        for key, value in metadata.items():
            if value is not None:
                where_clauses.append(f"r.{key} = ${key}")
                params[key] = value
        
        where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # 转换为大写
        if subj_type:
            subj_type = subj_type.upper()
        if obj_type:
            obj_type = obj_type.upper()
        if rel_type:
            rel_type = rel_type.upper()

        # 构建标签和关系类型查询
        subj_label = f":{subj_type}" if subj_type and self._validate_label(subj_type) else ""
        obj_label = f":{obj_type}" if obj_type and self._validate_label(obj_type) else ""
        rel_clause = f":{rel_type}" if rel_type and self._validate_label(rel_type) else ""
        
        cypher = f"""
            MATCH (s{subj_label})-[r{rel_clause}]->(o{obj_label})
            {where_str}
            RETURN r {{
                id: id(r),
                type: type(r),
                subject: {{
                    id: id(s),
                    name: s.name,
                    type: labels(s)[0]
                }},
                object: {{
                    id: id(o),
                    name: o.name,
                    type: labels(o)[0]
                }},
                metadata: properties(r) ,
                created_at: r.created_at,
                updated_at: r.updated_at                    
            }} AS relationship
            LIMIT $limit
        """
        params["limit"] = limit
        
        try:
            with self.driver.session() as session:
                results = session.run(cypher, **params)
                # ✅ 修改这里
                return self._serialize_result([record["relationship"] for record in results if record["relationship"]])
        except exceptions.Neo4jError as e:
            raise Exception(f"❌ 查询关系失败：{str(e)}")

    def update_relationship(
        self,
        subj_name: str,
        subj_type: str,
        rel_type: str,
        obj_name: str,
        obj_type: str,
        metadata: Dict
    ) -> Optional[Dict]:
        """
        更新关系属性
        
        Args:
            subj_name: 主体名称
            subj_type: 主体类型
            rel_type: 关系类型
            obj_name: 客体名称
            obj_type: 客体类型
            metadata: 要更新的属性字典
        
        Returns:
            更新后的关系信息
        """
        if not metadata:
            raise ValueError("更新属性不能为空")
        
        metadata = {k: v for k, v in metadata.items() if v is not None}
        
        # 转换为大写
        subj_type = subj_type.upper()
        rel_type = rel_type.upper()
        obj_type = obj_type.upper()
        
        cypher = f"""
            MATCH (s:{subj_type} {{name: $subj_name}})-[r:{rel_type}]->(o:{obj_type} {{name: $obj_name}})
            SET r += $metadata, r.updated_at = datetime()
            RETURN r {{
                id: id(r),
                type: type(r),
                subject: {{name: s.name, type: '{subj_type}'}},
                object: {{name: o.name, type: '{obj_type}'}},
                metadata: properties(r) ,
                created_at: r.created_at,
                updated_at: r.updated_at
            }} AS relationship
        """
        try:
            with self.driver.session() as session:
                result = session.run(
                    cypher,
                    subj_name=subj_name,
                    obj_name=obj_name,
                    metadata=metadata
                ).single()
                if not result:
                    raise Exception(f"关系({subj_type}:{subj_name})-[{rel_type}]->({obj_type}:{obj_name})不存在")
                # ✅ 修改这里
                return self._serialize_result(result["relationship"])
        except exceptions.Neo4jError as e:
            raise Exception(f"❌ 更新关系失败：{str(e)}")

    def delete_relationship(
        self,
        subj_name: str,
        subj_type: str,
        rel_type: str,
        obj_name: str,
        obj_type: str
    ) -> bool:
        """
        删除关系
        
        Args:
            subj_name: 主体名称
            subj_type: 主体类型
            rel_type: 关系类型
            obj_name: 客体名称
            obj_type: 客体类型
        
        Returns:
            删除成功返回True，失败返回False
        """
        # 转换为大写
        subj_type = subj_type.upper()
        rel_type = rel_type.upper()
        obj_type = obj_type.upper()
        
        cypher = f"""
            MATCH (s:{subj_type} {{name: $subj_name}})-[r:{rel_type}]->(o:{obj_type} {{name: $obj_name}})
            DELETE r
            RETURN count(r) AS deleted_count
        """
        try:
            with self.driver.session() as session:
                result = session.run(
                    cypher,
                    subj_name=subj_name,
                    obj_name=obj_name
                ).single()
                return result["deleted_count"] > 0 if result else False
        except exceptions.Neo4jError as e:
            raise Exception(f"❌ 删除关系失败：{str(e)}")

    def run_cypher(
        self,
        cypher: str,
        params: Optional[Dict] = None
    ) -> List[Dict]:
        """
        执行自定义Cypher查询
        
        Args:
            cypher: Cypher查询语句
            params: 查询参数字典（推荐使用参数化查询避免注入）
        
        Returns:
            查询结果列表
        """
        if not cypher or not isinstance(cypher, str):
            raise ValueError("Cypher语句不能为空")
        
        params = params or {}
        try:
            with self.driver.session() as session:
                result = session.run(cypher, **params)
                data = [record.data() for record in result]
                return self._serialize_result(data)
        except exceptions.Neo4jError as e:
            logger.error(f"⚠️ Cypher执行失败：{str(e)}，Cypher语句：{cypher}，参数：{params}")
            return []

    def get_graph_stats(self) -> Dict:
        """获取图谱统计信息"""
        cypher = """
            CALL apoc.meta.stats() YIELD labels, relTypesCount
            RETURN labels, relTypesCount
        """
        # 如果没有安装 APOC 插件，使用下面的备用查询（速度较慢但通用）：
        cypher_fallback = """
            MATCH (n)
            OPTIONAL MATCH ()-[r]->()
            RETURN count(DISTINCT n) as node_count, count(DISTINCT r) as rel_count
        """
        
        try:
            with self.driver.session() as session:
                # 尝试简单的统计
                result = session.run(cypher_fallback).single()
                stats = {
                    "node_count": result["node_count"],
                    "rel_count": result["rel_count"],
                    "label_distribution": {}, # 简单查询难以获取详细分布，先置空
                    "rel_type_distribution": {}
                }
                
                # 尝试获取详细 Label 分布 (分开查询以避免复杂语法错误)
                label_res = session.run("CALL db.labels() YIELD label RETURN label")
                for record in label_res:
                    label = record["label"]
                    count_res = session.run(f"MATCH (n:`{label}`) RETURN count(n) as c").single()
                    stats["label_distribution"][label] = count_res["c"]
                    
                return stats
        except Exception as e:
            logger.error(f"⚠️ 获取统计信息失败: {str(e)}")
            return {}

    def clear_database(self) -> bool:
        """
        清空整个数据库（谨慎使用！）
        
        Returns:
            清空成功返回True
        """
        confirm = input("⚠️ 警告：此操作将删除所有节点和关系，是否继续？(y/n)：")
        if confirm.lower() != "y":
            logger.info("✅ 已取消清空操作")
            return False
        
        cypher = """
            MATCH (n)
            DETACH DELETE n
            RETURN count(n) AS deleted_count
        """
        try:
            with self.driver.session() as session:
                result = session.run(cypher).single()
                logger.info(f"✅ 已删除 {result['deleted_count']} 个节点")
                return True
        except exceptions.Neo4jError as e:
            raise Exception(f"❌ 清空数据库失败：{str(e)}")

    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'driver') and self.driver:
            self.driver.close()
            logger.info("✅ Neo4j连接已关闭")

    def __del__(self):
        """析构函数：自动关闭连接"""
        self.close()

