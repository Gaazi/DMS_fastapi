from sqladmin import ModelView
from app.models.inventory import ItemCategory, InventoryItem, AssetIssue

class ItemCategoryAdmin(ModelView, model=ItemCategory):
    column_list = [ItemCategory.id, ItemCategory.name, ItemCategory.inst_id]
    category = "Inventory"
    icon = "fa-solid fa-tags"

class InventoryItemAdmin(ModelView, model=InventoryItem):
    column_list = [InventoryItem.id, InventoryItem.name, InventoryItem.item_type, InventoryItem.total_quantity, InventoryItem.available_quantity, InventoryItem.price, InventoryItem.inst_id]
    column_searchable_list = [InventoryItem.name, InventoryItem.isbn]
    category = "Inventory"
    icon = "fa-solid fa-boxes-stacked"

class AssetIssueAdmin(ModelView, model=AssetIssue):
    column_list = [AssetIssue.id, AssetIssue.item_id, AssetIssue.student_id, AssetIssue.staff_id, AssetIssue.issue_date, AssetIssue.is_returned]
    category = "Inventory"
    icon = "fa-solid fa-hand-holding"
