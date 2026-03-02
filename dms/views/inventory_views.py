from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from ..logic.inventory import InventoryManager
from ..helper import handle_manager_result
from ..logic.permissions import get_institution_with_access

@login_required
def inventory_dashboard(request, institution_slug):
    """انوینٹری اور لائبریری کا مرکزی صفحہ۔"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
    im = InventoryManager(request.user, institution=institution)
    
    if request.method == "POST":
        success, message, _ = im.create_new_item(request.POST)
        return handle_manager_result(request, success, message)
        
    context = im.get_inventory_context()
    return render(request, 'dms/inventory_list.html', context)

@login_required
def add_item_view(request, institution_slug):
    """نیا سامان / کتاب شامل کرنا۔"""
    if request.method == "POST":
        im = InventoryManager(request.user)
        success, message, _ = im.add_item(request.POST)
        return handle_manager_result(request, success, message)
    return redirect('inventory_dashboard', institution_slug=institution_slug)

@login_required
def issue_item_view(request, institution_slug):
    """سامان یا کتاب جاری کرنے کا عمل۔"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
    
    if request.method == "POST":
        im = InventoryManager(request.user, institution=institution)
        item_id = request.POST.get('item_id')
        student_id = request.POST.get('student_id') or None
        staff_id = request.POST.get('staff_id') or None
        quantity = request.POST.get('quantity', 1)
        due_date = request.POST.get('due_date') or None
        
        success, message, _ = im.issue_item(item_id, student_id, staff_id, quantity, due_date)
        return handle_manager_result(request, success, message)
    return redirect('inventory_dashboard', institution_slug=institution_slug)

@login_required
def return_item_view(request, institution_slug, issue_id):
    """سامان کی واپسی درج کرنا۔"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
    im = InventoryManager(request.user, institution=institution)
    success, message, _ = im.return_item(issue_id)
    return handle_manager_result(request, success, message)
