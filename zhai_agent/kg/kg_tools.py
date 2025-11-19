from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from .kg_manager import KGManager
import json
import logging

logger = logging.getLogger(__name__)

# ==================== 工具参数模型 ====================

class EntityCreateInput(BaseModel):
    """创建实体的输入参数"""
    name: str = Field(description="实体名称")
    entity_type: str = Field(description="实体类型", default="Entity")
    properties: Dict[str, Any] = Field(description="实体属性字典", default_factory=dict)

class RelationshipCreateInput(BaseModel):
    """创建关系的输入参数"""
    subject_name: str = Field(description="主体实体名称")
    subject_type: str = Field(description="主体实体类型", default="Entity")
    predicate: str = Field(description="谓语（关系类型）")
    object_name: str = Field(description="客体实体名称") 
    object_type: str = Field(description="客体实体类型", default="Entity")
    properties: Dict[str, Any] = Field(description="关系属性字典", default_factory=dict)

class KnowledgeTripleInput(BaseModel):
    """创建知识三元组的输入参数"""
    subject: str = Field(description="主语")
    predicate: str = Field(description="谓语（关系）")
    object: str = Field(description="宾语")
    subject_type: str = Field(description="主语类型", default="Entity")
    object_type: str = Field(description="宾语类型", default="Entity")
    properties: Dict[str, Any] = Field(description="关系属性", default_factory=dict)

class EntitySearchInput(BaseModel):
    """搜索实体的输入参数"""
    keyword: str = Field(description="搜索关键词")
    entity_type: Optional[str] = Field(description="实体类型过滤", default=None)
    limit: int = Field(description="返回结果数量限制", default=10)

class EntityGetInput(BaseModel):
    """获取实体的输入参数"""
    name: str = Field(description="实体名称")
    entity_type: Optional[str] = Field(description="实体类型", default=None)

class BatchImportInput(BaseModel):
    """批量导入的输入参数"""
    triples: List[List[str]] = Field(description="三元组列表，每个三元组为[subject, predicate, object]")
    entity_type_map: Optional[Dict[str, str]] = Field(description="实体类型映射", default_factory=dict)

# ==================== 知识图谱工具 ====================

class KGTools:
    """知识图谱工具集合"""
    
    def __init__(self):
        self.kg_manager = KGManager()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.kg_manager.close()

# 创建实体工具
@tool("kg_create_entity", args_schema=EntityCreateInput, return_direct=False)
def create_entity(name: str, entity_type: str = "Entity", properties: Dict[str, Any] = None) -> str:
    """
    在知识图谱中创建实体节点。
    
    如果实体已存在，则更新其属性。
    适用于创建人物、组织、地点、概念等各种实体。
    """
    try:
        with KGTools() as tools:
            success = tools.kg_manager.create_entity(name, entity_type, properties or {})
            if success:
                return f"✅ 成功创建实体: {name} ({entity_type})"
            else:
                return f"❌ 创建实体失败: {name} ({entity_type})"
    except Exception as e:
        logger.error(f"创建实体工具出错: {str(e)}")
        return f"❌ 创建实体时发生错误: {str(e)}"

# 创建关系工具
@tool("kg_create_relationship", args_schema=RelationshipCreateInput, return_direct=False)
def create_relationship(
    subject_name: str, 
    predicate: str, 
    object_name: str,
    subject_type: str = "Entity",
    object_type: str = "Entity",
    properties: Dict[str, Any] = None
) -> str:
    """
    在知识图谱中创建两个实体之间的关系。
    
    适用于建立人物关系、组织关系、概念关联等各种关系。
    如果实体不存在，需要先创建实体。
    """
    try:
        with KGTools() as tools:
            success = tools.kg_manager.create_relationship(
                subject_name, subject_type, predicate, 
                object_name, object_type, properties or {}
            )
            if success:
                return f"✅ 成功创建关系: {subject_name} -[{predicate}]-> {object_name}"
            else:
                return f"❌ 创建关系失败: {subject_name} -[{predicate}]-> {object_name}"
    except Exception as e:
        logger.error(f"创建关系工具出错: {str(e)}")
        return f"❌ 创建关系时发生错误: {str(e)}"

# 创建知识三元组工具（自动创建实体和关系）
@tool("kg_create_knowledge_triple", args_schema=KnowledgeTripleInput, return_direct=False)
def create_knowledge_triple(
    subject: str,
    predicate: str, 
    object: str,
    subject_type: str = "Entity",
    object_type: str = "Entity",
    properties: Dict[str, Any] = None
) -> str:
    """
    在知识图谱中创建知识三元组（主语-谓语-宾语）。
    
    这个工具会自动创建主语和宾语实体（如果不存在），然后建立它们之间的关系。
    适用于从自然语言中提取的知识进行结构化存储。
    
    示例:
    - 主语: "苹果公司", 谓语: "总部位于", 宾语: "库比蒂诺"
    - 主语: "张三", 谓语: "工作于", 宾语: "腾讯公司"
    - 主语: "机器学习", 谓语: "属于", 宾语: "人工智能"
    """
    try:
        with KGTools() as tools:
            success = tools.kg_manager.create_knowledge_triple(
                subject, predicate, object, 
                subject_type, object_type, properties or {}
            )
            if success:
                return f"✅ 成功创建知识三元组: {subject} -[{predicate}]-> {object}"
            else:
                return f"❌ 创建知识三元组失败: {subject} -[{predicate}]-> {object}"
    except Exception as e:
        logger.error(f"创建知识三元组工具出错: {str(e)}")
        return f"❌ 创建知识三元组时发生错误: {str(e)}"

# 搜索实体工具
@tool("kg_search_entities", args_schema=EntitySearchInput, return_direct=False)
def search_entities(keyword: str, entity_type: str = None, limit: int = 10) -> str:
    """
    在知识图谱中搜索实体。
    
    支持模糊搜索，可以按实体类型进行过滤。
    适用于查找已存在的实体，避免重复创建。
    """
    try:
        with KGTools() as tools:
            entities = tools.kg_manager.search_entities(keyword, entity_type, limit)
            
            if not entities:
                return f"🔍 未找到包含 '{keyword}' 的实体"
            
            result = f"🔍 找到 {len(entities)} 个包含 '{keyword}' 的实体:\n\n"
            for i, entity in enumerate(entities, 1):
                name = entity.get('name', '未知')
                entity_type_info = entity.get('labels', ['Entity'])[0] if 'labels' in entity else 'Entity'
                properties = {k: v for k, v in entity.items() if k not in ['name', 'labels']}
                
                result += f"{i}. {name} ({entity_type_info})\n"
                if properties:
                    result += f"   属性: {json.dumps(properties, ensure_ascii=False, indent=2)}\n"
                result += "\n"
            
            return result.strip()
    except Exception as e:
        logger.error(f"搜索实体工具出错: {str(e)}")
        return f"❌ 搜索实体时发生错误: {str(e)}"

# 获取实体信息工具
@tool("kg_get_entity", args_schema=EntityGetInput, return_direct=False)
def get_entity(name: str, entity_type: str = None) -> str:
    """
    获取知识图谱中特定实体的详细信息。
    
    包括实体的属性、关系等信息。
    """
    try:
        with KGTools() as tools:
            entity = tools.kg_manager.get_entity(name, entity_type)
            
            if not entity:
                return f"❌ 实体不存在: {name}"
            
            # 获取实体关系
            relationships = tools.kg_manager.get_relationships(name, entity_type)
            
            result = f"📋 实体信息: {name}\n"
            result += "=" * 50 + "\n\n"
            
            # 显示属性
            properties = {k: v for k, v in entity.items() if k not in ['name', 'labels']}
            if properties:
                result += f"属性:\n{json.dumps(properties, ensure_ascii=False, indent=2)}\n\n"
            
            # 显示关系
            if relationships:
                result += f"关系 ({len(relationships)} 个):\n"
                for rel in relationships:
                    rel_type = rel.get('rel_type', '未知关系')
                    other_name = rel.get('other_name', '未知')
                    other_labels = rel.get('other_labels', [])
                    other_type = other_labels[0] if other_labels else 'Entity'
                    
                    result += f"  - {rel_type} -> {other_name} ({other_type})\n"
                    
                    rel_props = rel.get('rel_props', {})
                    if rel_props:
                        result += f"    关系属性: {json.dumps(rel_props, ensure_ascii=False)}\n"
            else:
                result += "关系: 暂无关系\n"
            
            return result
    except Exception as e:
        logger.error(f"获取实体信息工具出错: {str(e)}")
        return f"❌ 获取实体信息时发生错误: {str(e)}"

# 批量导入三元组工具
@tool("kg_batch_import_triples", args_schema=BatchImportInput, return_direct=False)
def batch_import_triples(triples: List[List[str]], entity_type_map: Dict[str, str] = None) -> str:
    """
    批量导入知识三元组到知识图谱。
    
    适用于从结构化数据或自然语言处理结果中批量导入知识。
    每个三元组应该是 [subject, predicate, object] 格式。
    
    示例:
    triples = [
        ["苹果公司", "总部位于", "库比蒂诺"],
        ["乔布斯", "创立", "苹果公司"],
        ["iPhone", "由", "苹果公司"]
    ]
    """
    try:
        if not triples:
            return "❌ 三元组列表为空"
        
        # 验证三元组格式
        valid_triples = []
        for i, triple in enumerate(triples):
            if len(triple) != 3:
                return f"❌ 第 {i+1} 个三元组格式错误，应为 [subject, predicate, object]"
            valid_triples.append(tuple(triple))
        
        with KGTools() as tools:
            success = tools.kg_manager.import_from_triples(valid_triples, entity_type_map or {})
            
            if success:
                return f"✅ 成功导入 {len(valid_triples)} 个三元组到知识图谱"
            else:
                return f"❌ 导入三元组失败"
    except Exception as e:
        logger.error(f"批量导入三元组工具出错: {str(e)}")
        return f"❌ 批量导入三元组时发生错误: {str(e)}"

# 获取图统计信息工具
@tool("kg_get_graph_stats", return_direct=False)
def get_graph_stats() -> str:
    """
    获取知识图谱的统计信息。
    
    包括节点总数、关系总数、实体类型分布、关系类型分布等。
    适用于了解知识图谱的整体情况。
    """
    try:
        with KGTools() as tools:
            stats = tools.kg_manager.get_graph_stats()
            
            if not stats:
                return "❌ 无法获取图统计信息"
            
            result = "📊 知识图谱统计信息\n"
            result += "=" * 50 + "\n\n"
            
            result += f"节点总数: {stats.get('node_count', 0)}\n"
            result += f"关系总数: {stats.get('rel_count', 0)}\n\n"
            
            # 实体类型分布
            label_dist = stats.get('label_distribution', {})
            if label_dist:
                result += "实体类型分布:\n"
                for labels, count in label_dist.items():
                    label_str = ', '.join(labels) if isinstance(labels, (list, tuple)) else str(labels)
                    result += f"  - {label_str}: {count} 个\n"
                result += "\n"
            
            # 关系类型分布
            rel_dist = stats.get('rel_type_distribution', {})
            if rel_dist:
                result += "关系类型分布:\n"
                for rel_type, count in rel_dist.items():
                    result += f"  - {rel_type}: {count} 个\n"
            
            return result.strip()
    except Exception as e:
        logger.error(f"获取图统计信息工具出错: {str(e)}")
        return f"❌ 获取图统计信息时发生错误: {str(e)}"

# ==================== 工具列表 ====================

def get_kg_tools() -> List:
    """
    获取所有知识图谱工具的列表
    
    Returns:
        List: 知识图谱工具列表
    """
    return [
        create_entity,
        create_relationship, 
        create_knowledge_triple,
        search_entities,
        get_entity,
        batch_import_triples,
        get_graph_stats
    ]

# 导出工具函数
__all__ = [
    'get_kg_tools',
    'create_entity',
    'create_relationship',
    'create_knowledge_triple',
    'search_entities',
    'get_entity',
    'batch_import_triples',
    'get_graph_stats'
]