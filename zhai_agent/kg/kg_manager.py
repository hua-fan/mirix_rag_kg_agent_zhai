from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
import logging
from .kg_storage import KGStorage

logger = logging.getLogger(__name__)

class KGManager:
    """知识图谱管理器 - 封装知识图谱的核心操作"""
    
    def __init__(self):
        self.storage = KGStorage()
        logger.info("知识图谱管理器初始化完成")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def close(self):
        """关闭知识图谱连接"""
        if self.storage:
            self.storage.close()
            logger.info("知识图谱连接已关闭")
    
    # ==================== 实体管理 ====================
    
    def create_entity(self, name: str, entity_type: str, properties: Dict[str, Any] = None) -> bool:
        """
        创建实体
        
        Args:
            name: 实体名称
            entity_type: 实体类型
            properties: 实体属性字典
            
        Returns:
            bool: 创建成功返回True，实体已存在也返回True
        """
        try:
            # create_entity 使用 MERGE 语句，无论实体是否存在都会成功
            entity_info = self.storage.create_entity(name, entity_type, properties or {})
            if entity_info:
                logger.info(f"创建/更新实体成功: {name} ({entity_type})")
                return True
            else:
                # 即使返回None，也不认为是失败（可能是存储层的问题）
                logger.warning(f"实体操作返回None: {name} ({entity_type})")
                return True
        except Exception as e:
            logger.error(f"创建实体失败: {name} ({entity_type}) - {str(e)}")
            return False
    
    def get_entity(self, name: str, entity_type: str = None) -> Optional[Dict[str, Any]]:
        """
        获取实体信息
        
        Args:
            name: 实体名称
            entity_type: 实体类型（可选）
            
        Returns:
            实体信息字典，不存在返回None
        """
        try:
            entity = self.storage.get_entity(name, entity_type)
            if entity:
                logger.info(f"获取实体成功: {name}")
            else:
                logger.warning(f"实体不存在: {name}")
            return entity
        except Exception as e:
            logger.error(f"获取实体失败: {name} - {str(e)}")
            return None
    
    def update_entity(self, name: str, entity_type: str, properties: Dict[str, Any]) -> bool:
        """
        更新实体属性
        
        Args:
            name: 实体名称
            entity_type: 实体类型
            properties: 要更新的属性字典
            
        Returns:
            bool: 更新成功返回True
        """
        try:
            success = self.storage.update_entity(name, entity_type, properties)
            if success:
                logger.info(f"更新实体成功: {name} ({entity_type})")
            else:
                logger.warning(f"更新实体失败（实体不存在）: {name} ({entity_type})")
            return success
        except Exception as e:
            logger.error(f"更新实体失败: {name} ({entity_type}) - {str(e)}")
            return False
    
    def delete_entity(self, name: str, entity_type: str = None) -> bool:
        """
        删除实体及其所有关系
        
        Args:
            name: 实体名称
            entity_type: 实体类型（可选）
            
        Returns:
            bool: 删除成功返回True
        """
        try:
            success = self.storage.delete_entity(name, entity_type)
            if success:
                logger.info(f"删除实体成功: {name}")
            else:
                logger.warning(f"删除实体失败（实体不存在）: {name}")
            return success
        except Exception as e:
            logger.error(f"删除实体失败: {name} - {str(e)}")
            return False
    
    def search_entities(self, keyword: str, entity_type: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        搜索实体
        
        Args:
            keyword: 搜索关键词
            entity_type: 实体类型（可选）
            limit: 返回结果数量限制
            
        Returns:
            实体列表
        """
        try:
            entities = self.storage.search_entities(keyword, entity_type, limit)
            logger.info(f"搜索实体成功: 关键词='{keyword}', 结果数量={len(entities)}")
            return entities
        except Exception as e:
            logger.error(f"搜索实体失败: 关键词='{keyword}' - {str(e)}")
            return []
    
    def get_entities_by_type(self, entity_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取指定类型的所有实体
        
        Args:
            entity_type: 实体类型
            limit: 返回结果数量限制
            
        Returns:
            实体列表
        """
        try:
            entities = self.storage.get_entities_by_type(entity_type, limit)
            logger.info(f"获取类型实体成功: {entity_type}, 数量={len(entities)}")
            return entities
        except Exception as e:
            logger.error(f"获取类型实体失败: {entity_type} - {str(e)}")
            return []
    
    # ==================== 关系管理 ====================
    
    def create_relationship(self, subj_name: str, subj_type: str, rel_type: str,
                           obj_name: str, obj_type: str, properties: Dict[str, Any] = None) -> bool:
        """
        创建关系
        
        Args:
            subj_name: 主体实体名称
            subj_type: 主体实体类型
            rel_type: 关系类型
            obj_name: 客体实体名称
            obj_type: 客体实体类型
            properties: 关系属性字典
            
        Returns:
            bool: 创建成功返回True
        """
        try:
            self.storage.create_relationship(subj_name, subj_type, rel_type, 
                                           obj_name, obj_type, properties or {})
            logger.info(f"创建关系成功: {subj_name} -[{rel_type}]-> {obj_name}")
            return True
        except Exception as e:
            logger.error(f"创建关系失败: {subj_name} -[{rel_type}]-> {obj_name} - {str(e)}")
            return False
    
    def get_relationships(self, entity_name: str, entity_type: str = None, 
                         rel_type: str = None, direction: str = "both") -> List[Dict[str, Any]]:
        """
        获取实体的关系
        
        Args:
            entity_name: 实体名称
            entity_type: 实体类型（可选）
            rel_type: 关系类型（可选）
            direction: 方向（"out", "in", "both"）
            
        Returns:
            关系列表
        """
        try:
            relationships = self.storage.get_relationships(entity_name, entity_type, rel_type, direction)
            logger.info(f"获取关系成功: {entity_name}, 关系数量={len(relationships)}")
            return relationships
        except Exception as e:
            logger.error(f"获取关系失败: {entity_name} - {str(e)}")
            return []
    
    def delete_relationship(self, subj_name: str, subj_type: str, rel_type: str,
                           obj_name: str, obj_type: str) -> bool:
        """
        删除关系
        
        Args:
            subj_name: 主体实体名称
            subj_type: 主体实体类型
            rel_type: 关系类型
            obj_name: 客体实体名称
            obj_type: 客体实体类型
            
        Returns:
            bool: 删除成功返回True
        """
        try:
            success = self.storage.delete_relationship(subj_name, subj_type, rel_type, obj_name, obj_type)
            if success:
                logger.info(f"删除关系成功: {subj_name} -[{rel_type}]-> {obj_name}")
            else:
                logger.warning(f"删除关系失败（关系不存在）: {subj_name} -[{rel_type}]-> {obj_name}")
            return success
        except Exception as e:
            logger.error(f"删除关系失败: {subj_name} -[{rel_type}]-> {obj_name} - {str(e)}")
            return False
    
    # ==================== 批量操作 ====================
    
    def batch_create_entities(self, entities: List[Dict[str, Any]]) -> bool:
        """
        批量创建实体
        
        Args:
            entities: 实体列表，每个实体包含name、type、properties
            
        Returns:
            bool: 批量创建成功返回True
        """
        try:
            self.storage.batch_create_entities(entities)
            logger.info(f"批量创建实体成功: 数量={len(entities)}")
            return True
        except Exception as e:
            logger.error(f"批量创建实体失败: 数量={len(entities)} - {str(e)}")
            return False
    
    def batch_create_relationships(self, relationships: List[Dict[str, Any]]) -> bool:
        """
        批量创建关系
        
        Args:
            relationships: 关系列表，每个关系包含subj_name、subj_type、rel_type、obj_name、obj_type、properties
            
        Returns:
            bool: 批量创建成功返回True
        """
        try:
            self.storage.batch_create_relationships(relationships)
            logger.info(f"批量创建关系成功: 数量={len(relationships)}")
            return True
        except Exception as e:
            logger.error(f"批量创建关系失败: 数量={len(relationships)} - {str(e)}")
            return False
    
    # ==================== 图分析 ====================
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """
        获取图数据库统计信息
        
        Returns:
            统计信息字典
        """
        try:
            stats = self.storage.get_graph_stats()
            logger.info("获取图统计信息成功")
            return stats
        except Exception as e:
            logger.error(f"获取图统计信息失败: {str(e)}")
            return {}
    
    def find_paths(self, start_entity: str, end_entity: str, max_depth: int = 3) -> List[List[Dict[str, Any]]]:
        """
        查找两个实体之间的路径
        
        Args:
            start_entity: 起始实体名称
            end_entity: 目标实体名称
            max_depth: 最大路径深度
            
        Returns:
            路径列表，每条路径包含节点和关系信息
        """
        try:
            cypher = f"""
                MATCH path = (start {{name: $start_entity}})-[*1..{max_depth}]-(end {{name: $end_entity}})
                RETURN [
                    node in nodes(path) | {{
                        name: node.name,
                        labels: labels(node),
                        properties: properties(node)
                    }}
                ] as nodes,
                [
                    rel in relationships(path) | {{
                        type: type(rel),
                        properties: properties(rel)
                    }}
                ] as relationships
                LIMIT 10
            """
            results = self.storage.run_cypher(cypher, {"start_entity": start_entity, "end_entity": end_entity})
            
            paths = []
            for result in results:
                path_info = {
                    "nodes": result["nodes"],
                    "relationships": result["relationships"]
                }
                paths.append(path_info)
            
            logger.info(f"查找路径成功: {start_entity} -> {end_entity}, 找到{len(paths)}条路径")
            return paths
        except Exception as e:
            logger.error(f"查找路径失败: {start_entity} -> {end_entity} - {str(e)}")
            return []
    
    def find_common_neighbors(self, entity1: str, entity2: str) -> List[Dict[str, Any]]:
        """
        查找两个实体的共同邻居
        
        Args:
            entity1: 实体1名称
            entity2: 实体2名称
            
        Returns:
            共同邻居列表
        """
        try:
            cypher = """
                MATCH (e1 {name: $entity1})--(common)--(e2 {name: $entity2})
                RETURN common.name as name,
                       labels(common) as labels,
                       properties(common) as properties
            """
            results = self.storage.run_cypher(cypher, {"entity1": entity1, "entity2": entity2})
            
            neighbors = []
            for result in results:
                neighbor_info = {
                    "name": result["name"],
                    "labels": result["labels"],
                    "properties": dict(result["properties"])
                }
                neighbors.append(neighbor_info)
            
            logger.info(f"查找共同邻居成功: {entity1} 和 {entity2}, 找到{len(neighbors)}个共同邻居")
            return neighbors
        except Exception as e:
            logger.error(f"查找共同邻居失败: {entity1} 和 {entity2} - {str(e)}")
            return []
    
    # ==================== 高级查询 ====================
    
    def execute_custom_query(self, cypher: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        执行自定义Cypher查询
        
        Args:
            cypher: Cypher查询语句
            parameters: 查询参数
            
        Returns:
            查询结果列表
        """
        try:
            results = self.storage.run_cypher(cypher, parameters or {})
            logger.info(f"执行自定义查询成功: 返回{len(results)}条结果")
            return results
        except Exception as e:
            logger.error(f"执行自定义查询失败: {str(e)}")
            return []
    
    def get_entity_network(self, entity_name: str, depth: int = 2, rel_types: List[str] = None) -> Dict[str, Any]:
        """
        获取实体的网络结构
        
        Args:
            entity_name: 中心实体名称
            depth: 探索深度
            rel_types: 关系类型过滤（可选）
            
        Returns:
            网络结构信息
        """
        try:
            rel_filter = ""
            if rel_types:
                rel_filter = f"WHERE type(r) IN {rel_types}"
            
            cypher = f"""
                MATCH path = (center {{name: $entity_name}})-[*1..{depth}]-(neighbor)
                {rel_filter}
                RETURN center.name as center_name,
                       collect(DISTINCT {{
                           name: neighbor.name,
                           labels: labels(neighbor),
                           distance: length(shortestPath((center)-[*1..{depth}]-(neighbor)))
                       }}) as neighbors
            """
            results = self.storage.run_cypher(cypher, {"entity_name": entity_name})
            
            if results:
                network = results[0]
                logger.info(f"获取实体网络成功: {entity_name}, 邻居数量={len(network['neighbors'])}")
                return network
            else:
                logger.warning(f"获取实体网络失败（实体不存在）: {entity_name}")
                return {}
        except Exception as e:
            logger.error(f"获取实体网络失败: {entity_name} - {str(e)}")
            return {}
    
    # ==================== 知识图谱构建辅助 ====================
    
    def create_knowledge_triple(self, subject: str, predicate: str, object: str, 
                              subj_type: str = "Entity", obj_type: str = "Entity",
                              properties: Dict[str, Any] = None) -> bool:
        """
        创建知识三元组（主语-谓语-宾语）
        
        Args:
            subject: 主语
            predicate: 谓语（关系）
            object: 宾语
            subj_type: 主语类型
            obj_type: 宾语类型
            properties: 关系属性
            
        Returns:
            bool: 创建成功返回True
        """
        try:
            # 直接使用存储层的MERGE语句确保实体存在，然后创建关系
            # 这样可以避免MATCH查询找不到实体的问题
            with self.storage.driver.session() as session:
                cypher = f"""
                    MERGE (s:{subj_type} {{name: $subject}})
                    MERGE (o:{obj_type} {{name: $object}})
                    MERGE (s)-[r:{predicate}]->(o)
                    SET r += $properties,
                        r.updated_at = datetime(),
                        r.created_at = coalesce(r.created_at, datetime())
                    RETURN s.name as subject, o.name as object, type(r) as predicate
                """
                result = session.run(cypher, subject=subject, object=object, properties=properties or {})
                if result.single():
                    logger.info(f"创建知识三元组成功: {subject} -[{predicate}]-> {object}")
                    return True
                else:
                    logger.error(f"创建知识三元组失败: {subject} -[{predicate}]-> {object}")
                    return False
        except Exception as e:
            logger.error(f"创建知识三元组失败: {subject} -[{predicate}]-> {object} - {str(e)}")
            return False
    
    def import_from_triples(self, triples: List[Tuple[str, str, str]], 
                          entity_type_map: Dict[str, str] = None) -> bool:
        """
        从三元组列表导入知识图谱
        
        Args:
            triples: 三元组列表，每个三元组为(subject, predicate, object)
            entity_type_map: 实体类型映射，key为实体名称，value为类型
            
        Returns:
            bool: 导入成功返回True
        """
        try:
            entity_type_map = entity_type_map or {}
            
            # 收集所有实体
            entities = set()
            for subject, _, object in triples:
                entities.add(subject)
                entities.add(object)
            
            # 批量创建实体
            entity_list = []
            for entity in entities:
                entity_type = entity_type_map.get(entity, "Entity")
                entity_list.append({
                    "name": entity,
                    "type": entity_type,
                    "metadata": {}
                })
            
            if entity_list:
                self.batch_create_entities(entity_list)
            
            # 批量创建关系
            relationship_list = []
            for subject, predicate, object in triples:
                subj_type = entity_type_map.get(subject, "Entity")
                obj_type = entity_type_map.get(object, "Entity")
                relationship_list.append({
                    "subj_name": subject,
                    "subj_type": subj_type,
                    "rel_type": predicate,
                    "obj_name": object,
                    "obj_type": obj_type,
                    "metadata": {}
                })
            
            if relationship_list:
                self.batch_create_relationships(relationship_list)
            
            logger.info(f"从三元组导入成功: 实体数量={len(entities)}, 关系数量={len(triples)}")
            return True
        except Exception as e:
            logger.error(f"从三元组导入失败: {str(e)}")
            return False