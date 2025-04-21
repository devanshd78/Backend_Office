import re
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from db import db  # MongoDB connection for employees, subadmin, admin collections
import uuid

# Blueprint for subadmin routes
subadmin_bp = Blueprint('subadmin', __name__, url_prefix='/subadmin')

# Permission mapping: JSON field -> human-readable
PERMISSIONS = {
    'View payslip details': 'View payslip details',
    'Generate payslip': 'Generate payslip',
    'View Invoice details': 'View Invoice details',
    'Generate invoice details': 'Generate invoice details',
    'Add Employee Details': 'Add Employee details',
    'View Employee Details': 'View employee details',
}

# Password complexity: uppercase, lowercase, digit, special char, min length 8
PASSWORD_REGEX = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$')

@subadmin_bp.route('/register', methods=['POST'])
def register_subadmin():
    data = request.get_json() or {}
    admin_id    = data.get('adminid')
    employee_id = data.get('employeeid')
    username    = data.get('username')
    password    = data.get('password')
    perms       = data.get('permissions', {})

    if not all([admin_id, employee_id, username, password]):
        return jsonify({'error': 'Missing required fields: adminid, employeeid, username, or password'}), 400

    if not db.admin.find_one({'adminId': admin_id}):
        return jsonify({'error': 'Invalid adminId'}), 403

    if not PASSWORD_REGEX.match(password):
        return jsonify({'error': 'Password must be at least 8 chars and include uppercase, lowercase, number, special char'}), 400

    if not db.employees.find_one({'employeeId': employee_id}):
        return jsonify({'error': 'No such employee'}), 404

    if db.subadmin.find_one({'employeeId': employee_id}):
        return jsonify({'error': 'Subadmin credentials already exist for this employee, please login'}), 409

    if db.subadmin.find_one({'username': username}):
        return jsonify({'error': 'Username already taken'}), 409

    pw_hash = generate_password_hash(password)
    permission_flags = { key: int(bool(perms.get(key))) for key in PERMISSIONS.keys() }

    subadmin_id = str(uuid.uuid4())  # Generate unique subadmin ID

    db.subadmin.insert_one({
        'subadminId': subadmin_id,
        'employeeId': employee_id,
        'username': username,
        'password_hash': pw_hash,
        'permissions': permission_flags
    })

    return jsonify({'message': 'Subadmin registered successfully', 'subadminId': subadmin_id}), 200

@subadmin_bp.route('/updaterecord', methods=['POST'])
def update_subadmin():
    data = request.get_json() or {}
    subadmin_id = data.get('subadminid')
    updates = data.get('updates', {})

    if not subadmin_id:
        return jsonify({'error': 'subadminid is required'}), 400

    existing = db.subadmin.find_one({'subadminId': subadmin_id})
    if not existing:
        return jsonify({'error': 'Subadmin not found'}), 404

    update_fields = {}

    if 'username' in updates:
        if db.subadmin.find_one({'username': updates['username'], 'subadminId': {'$ne': subadmin_id}}):
            return jsonify({'error': 'Username already in use'}), 409
        update_fields['username'] = updates['username']

    if 'password' in updates:
        if not PASSWORD_REGEX.match(updates['password']):
            return jsonify({'error': 'Password must be at least 8 chars and include uppercase, lowercase, number, special char'}), 400
        update_fields['password_hash'] = generate_password_hash(updates['password'])

    if 'permissions' in updates:
        perms = updates['permissions']
        update_fields['permissions'] = { key: int(bool(perms.get(key))) for key in PERMISSIONS.keys() }

    if not update_fields:
        return jsonify({'error': 'No valid fields to update'}), 400

    db.subadmin.update_one({'subadminId': subadmin_id}, {'$set': update_fields})
    return jsonify({'message': 'Subadmin updated successfully'}), 200

@subadmin_bp.route('/deleterecord', methods=['POST'])
def delete_subadmin():
    data = request.get_json() or {}
    subadmin_id = data.get('subadminId')

    if not subadmin_id:
        return jsonify({'error': 'Missing required field: subadminid'}), 400

    result = db.subadmin.delete_one({'subadminId': subadmin_id})
    if result.deleted_count == 0:
        return jsonify({'error': 'Subadmin not found'}), 404

    return jsonify({'message': 'Subadmin deleted successfully'}), 200

@subadmin_bp.route('/getlist', methods=['POST'])
def get_subadmin_list():
    data = request.get_json() or {}

    page = int(data.get('page', 1))
    page_size = int(data.get('pageSize', 10))
    search = data.get('search', '').strip()

    query = {}
    if search:
        query['$or'] = [
            {'username': {'$regex': search, '$options': 'i'}},
            {'employeeId': {'$regex': search, '$options': 'i'}}
        ]

    total = db.subadmin.count_documents(query)

    subadmins = list(db.subadmin.find(
        query,
        {'_id': 0, 'password_hash': 0}
    )
    .skip((page - 1) * page_size)
    .limit(page_size))

    return jsonify({
        'success': True,
        'data': {
            'subadmins': subadmins,
            'total': total,
            'page': page,
            'pageSize': page_size
        }
    }), 200
    
@subadmin_bp.route('/login', methods=['POST'])
def login_subadmin():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')

    if not all([username, password]):
        return jsonify({'error': 'Missing username or password'}), 400

    user = db.subadmin.find_one({'username': username})
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid credentials'}), 401

    # Return raw permission flags as key:0/1 map
    return jsonify({
        'role': 'subadmin',
        'permissions': user.get('permissions', {})
    }), 200
