from flask import Flask, request, jsonify,Blueprint, send_file
from flask_pymongo import PyMongo
from bson import ObjectId
from datetime import datetime
from db import db
import re
import math
import random
import string
from salaryslip import SalarySlipGenerator
import calendar
from datetime import datetime
import uuid
from io import BytesIO
import os

employee_bp = Blueprint('employee', __name__,url_prefix='/employee')

# Helper function for formatting consistent responses
def format_response(success, message, data=None, status_code=200):
    return jsonify({
        "success": success,
        "message": message,
        "data": data or {}
    }), status_code


def generate_unique_employee_id():
    while True:
        emp_id = "EMP" + ''.join(random.choices(string.digits, k=4))
        if not db.employees.find_one({"employeeId": emp_id}):
            return emp_id

@employee_bp.route('/SaveRecord', methods=['POST'])
def add_employee():
    try:
        data = request.get_json()

        name = data.get("name")
        email = data.get("email")
        phone = data.get("phone")
        dob = data.get("dob")
        adharnumber = data.get("adharnumber")
        pan_number = data.get("pan_number")
        date_of_joining = data.get("date_of_joining")
        annual_salary = data.get("annual_salary")
        base_salary = data.get("base_salary")
        department = data.get("department")
        designation = data.get("designation")
        bank_details = data.get("bank_details")
        address = data.get("address")

        if not all([name, email, phone, dob, adharnumber, pan_number, date_of_joining, annual_salary, department, designation, base_salary]):
            return format_response(False, "Missing required employee details", status_code=400)

        # Uniqueness check: email or phone already exists
        existing_employee = db.employees.find_one({
            "$or": [
                {"email": email},
                {"phone": phone}
            ]
        })
        if existing_employee:
            return format_response(False, "Employee already exists with this email or phone number", status_code=409)

        # Validate date formats
        try:
            datetime.strptime(dob, "%Y-%m-%d")
            datetime.strptime(date_of_joining, "%Y-%m-%d")
        except ValueError:
            return format_response(False, "Date format must be YYYY-MM-DD", status_code=400)

        try:
            annual_salary = float(annual_salary)
        except ValueError:
            return format_response(False, "Annual salary must be a number", status_code=400)

        ctc = annual_salary

        # Generate unique employee ID like EMP1023
        employee_id = generate_unique_employee_id()

        employee_record = {
            "employeeId": employee_id,
            "name": name,
            "email": email,
            "phone": phone,
            "dob": dob,
            "adharnumber": adharnumber,
            "pan_number": pan_number,
            "date_of_joining": date_of_joining,
            "annual_salary": annual_salary,
            "monthly_salary": base_salary,
            "bank_details": bank_details,
            "address": address,
            "department": department,
            "designation": designation,
            "created_at": datetime.utcnow()
        }

        result = db.employees.insert_one(employee_record)

        return format_response(True, "Employee added successfully", {
            "employee_id": employee_id
        }, 201)

    except Exception as e:
        return format_response(False, str(e), status_code=500)

@employee_bp.route('/update', methods=['POST'])
def update_employee():
    """
    POST /employee/update
    Request JSON:
      {
        "employeeId": "<EMPxxxx>",    # required: your generated employeeId
        ...                           # any of the fields you wish to update:
          "name": "...",
          "email": "...",
          "phone": "...",
          "dob": "YYYY-MM-DD",
          "adharnumber": "...",
          "pan_number": "...",
          "date_of_joining": "YYYY-MM-DD",
          "annual_salary": <number>,
          "monthly_salary": <number>,
          "ctc": <number>,
          "bank_details": { "account_number": "...", "ifsc": "...", "bank_name": "..." },
          "address": { "line1": "...", "city": "...", "state": "...", "pin": "..." },
          "department": "...",
          "designation": "..."
      }
    Response JSON:
      {
        "success": true,
        "message": "Employee updated successfully.",
        "data": {
          "employeeId": "<EMPxxxx>"
        }
      }
    """
    try:
        data = request.get_json() or {}
        emp_id = data.get("employeeId")
        if not emp_id:
            return format_response(False, "employeeId is required", status_code=400)

        # Remove employeeId from the update payload
        update_fields = {k: v for k, v in data.items() if k != "employeeId"}

        if not update_fields:
            return format_response(False, "No fields provided for update", status_code=400)

        # Optional: validate dates
        for date_field in ("dob", "date_of_joining"):
            if date_field in update_fields:
                try:
                    datetime.strptime(update_fields[date_field], "%Y-%m-%d")
                except ValueError:
                    return format_response(False, f"{date_field} must be YYYY-MM-DD", status_code=400)

        # Perform the update
        result = db.employees.update_one(
            { "employeeId": emp_id },
            { "$set": update_fields }
        )

        if result.matched_count == 0:
            return format_response(False, "Employee not found", status_code=404)

        return format_response(True, "Employee updated successfully.", { "employeeId": emp_id }, 200)

    except Exception as e:
        return format_response(False, str(e), status_code=500)


@employee_bp.route('/delete', methods=['POST'])
def delete_employee():
    """
    POST /employee/delete
    Request JSON:
      {
        "employeeId": "<EMPxxxx>"   # required
      }
    Response JSON:
      {
        "success": true,
        "message": "Employee deleted successfully."
      }
    """
    try:
        data = request.get_json() or {}
        emp_id = data.get("employeeId")
        if not emp_id:
            return format_response(False, "employeeId is required", status_code=400)

        result = db.employees.delete_one({ "employeeId": emp_id })
        if result.deleted_count == 0:
            return format_response(False, "Employee not found", status_code=404)

        return format_response(True, "Employee deleted successfully.", {}, 200)

    except Exception as e:
        return format_response(False, str(e), status_code=500)

@employee_bp.route('/getrecord', methods=['GET'])
def get_record():
    """
    GET /employee/getrecord?employeeId=<EMPxxxx>
    
    Query Parameters:
      - employeeId (required): the custom employee ID (e.g., "EMP1023")
    
    Returns:
      200: { success: true, message, data: { employee: { ... } } }
      400: missing employeeId
      404: not found
      500: server error
    """
    emp_id = request.args.get('employeeId')
    if not emp_id:
        return format_response(False, "Query parameter 'employeeId' is required", status_code=400)

    try:
        emp = db.employees.find_one({ "employeeId": emp_id })
        if not emp:
            return format_response(False, "Employee not found", status_code=404)

        employee_data = {
            "employeeId": emp.get("employeeId"),
            "name": emp.get("name"),
            "email": emp.get("email"),
            "phone": emp.get("phone"),
            "dob": emp.get("dob"),
            "adharnumber": emp.get("adharnumber"),
            "pan_number": emp.get("pan_number"),
            "date_of_joining": emp.get("date_of_joining"),
            "annual_salary": emp.get("annual_salary"),
            "monthly_salary": emp.get("monthly_salary"),
            "ctc": emp.get("ctc"),
            "bank_details": emp.get("bank_details"),
            "address": emp.get("address"),
            "department": emp.get("department"),
            "designation": emp.get("designation"),
            "created_at": emp.get("created_at").isoformat() if emp.get("created_at") else None,
        }

        return format_response(True, "Employee retrieved successfully.", { "employee": employee_data }, 200)

    except Exception as e:
        return format_response(False, str(e), status_code=500)


@employee_bp.route('/getlist', methods=['POST'])
def get_all_employees():
    """
    POST /employee/getlist
    Request JSON:
      {
        "search": "<search term>",  # optional: name/email/phone matching
        "page": <page number, defaults to 1>,
        "pageSize": <records per page, defaults to 10>
      }
    Response JSON:
      {
        "success": true,
        "message": "Employees retrieved successfully.",
        "data": {
          "employees": [
            {"employeeId": ..., "name": ..., "email": ..., "phone": ..., "dob": ..., "address": ..., "bankDetails": ..., ...},
            ...
          ],
          "total": <total matching count>,
          "page": <current page>,
          "pageSize": <page size>,
          "totalPages": <number of pages>
        }
      }
    """
    try:
        payload = request.get_json() or {}
        search_term = (payload.get('search', '') or '').strip()
        page = max(int(payload.get('page', 1)), 1)
        page_size = max(int(payload.get('pageSize', 10)), 1)

        # Build MongoDB query
        query = {}
        if search_term:
            regex = re.compile(re.escape(search_term), re.IGNORECASE)
            query['$or'] = [
                {'name': regex},
                {'email': regex},
                {'phone': regex},
            ]

        # Count total documents
        total = db.employees.count_documents(query)
        skip = (page - 1) * page_size

        # Fetch paginated results
        cursor = db.employees.find(query).skip(skip).limit(page_size)
        employees_list = []
        for emp in cursor:
            employees_list.append({
                'employeeId': emp.get('employeeId'),
                'name': emp.get('name'),
                'email': emp.get('email'),
                'phone': emp.get('phone'),
                'dob': emp.get('dob'),
                'adharnumber': emp.get('adharnumber'),
                'pan_number': emp.get('pan_number'),
                'date_of_joining': emp.get('date_of_joining'),
                'annual_salary': emp.get('annual_salary'),
                'monthly_salary': emp.get('monthly_salary'),
                'ctc': emp.get('ctc'),
                'bank_details': emp.get('bank_details'),
                'address': emp.get('address'),
                'department': emp.get('department'),
                'designation': emp.get('designation'),
            })

        total_pages = math.ceil(total / page_size)
        response_data = {
            'employees': employees_list,
            'total': total,
            'page': page,
            'pageSize': page_size,
            'totalPages': total_pages,
        }

        return format_response(True, 'Employees retrieved successfully.', response_data, 200)

    except Exception as e:
        return format_response(False, f"Error: {str(e)}", {}, 500)

    
@employee_bp.route('/salaryslip', methods=['POST'])
def get_salary_slip():
    data = request.get_json() or {}
    employee_id  = data.get("employee_id")
    lop_days     = float(data.get("lop", 0))
    payslip_month = data.get("month")  # e.g. "04-2025"

    if not all([employee_id, payslip_month]):
        return jsonify({"success": False, "message": "Missing required fields: employee_id or month"}), 400

    try:
        # Parse "MM-YYYY" to date
        month_date = datetime.strptime(payslip_month, "%m-%Y")
        year = month_date.year
        month = month_date.month
        max_days = calendar.monthrange(year, month)[1]
        date_str = f"{max_days:02d}-{month:02d}-{year}"
    except ValueError:
        return jsonify({"success": False, "message": "Invalid month format. Use MM-YYYY"}), 400

    emp = db.employees.find_one({"employeeId": employee_id})
    if not emp:
        return jsonify({"success": False, "message": "Employee not found"}), 404

    incoming = data.get("salary_structure", [])
    incoming_map = { item["name"]: float(item.get("amount", 0)) for item in incoming }

    allowance_names = [
        "Basic Pay",
        "House Rent Allowance",
        "Conveyance Allowance",
        "Performance Bonas",
        "Overtime Bonas",
        "MED ALL",
        "OTH ALL"
    ]

    final_structure = []
    for name in allowance_names:
        amt = float(emp.get("monthly_salary", 0)) if name == "Basic Pay" else incoming_map.get(name, 0.0)
        final_structure.append({ "name": name, "amount": amt })

    emp_data = {
        "full_name":       emp.get("name"),
        "emp_no":          emp.get("employeeId"),
        "designation":     emp.get("designation", ""),
        "department":      emp.get("department", ""),
        "doj":             datetime.strptime(emp.get("date_of_joining"), "%Y-%m-%d").strftime("%d-%m-%Y"),
        "bank_account":    emp.get("bank_details", {}).get("account_number", ""),
        "pan":             emp.get("pan_number"),
        "lop":             lop_days,
        "salary_structure": final_structure,
    }

    # Step 1: Generate PDF
    generator = SalarySlipGenerator(emp_data, current_date=date_str)
    pdf_buf: BytesIO = generator.generate_pdf()

    # Step 2: Generate unique payslip ID
    payslip_id = str(uuid.uuid4())

    # Step 3: Store metadata in DB (you can extend this model)
    db.payslips.insert_one({
        "payslipId": payslip_id,
        "employeeId": employee_id,
        "month": month,
        "year": year,
        "generated_on": datetime.utcnow(),
        "lop_days": lop_days,
        "salary_structure": final_structure,
        "emp_snapshot": emp_data,  # Optional: for reference
        "filename": f"salary_slip_{employee_id}.pdf",
    })

    # Step 4: Return the PDF
    return send_file(
        pdf_buf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"salary_slip_{employee_id}.pdf"
    )
    
@employee_bp.route('/getpayslips', methods=['POST'])
def get_payslips():
    data = request.get_json() or {}
    
    # Extract filters and pagination parameters
    search = data.get('search', '')
    month = data.get('month', '')
    year = data.get('year', '')
    page = int(data.get('page', 1))  # Default to page 1
    page_size = int(data.get('pageSize', 10))  # Default to 10 items per page
    
    query = {}

    # Build query based on provided filters
    if search:
        query["$text"] = {"$search": search}  # Text search for employee name or other fields
    if month:
        query["month"] = month
    if year:
        query["year"] = year

    # Fetch the total count of payslips based on the filters (for pagination)
    total_payslips = db.payslips.count_documents(query)

    # Fetch the payslips data (paginated)
    payslips = list(db.payslips.find(query, {"_id": 0})  # Exclude MongoDB _id
                    .skip((page - 1) * page_size)  # Pagination offset
                    .limit(page_size))  # Pagination limit

    if not payslips:
        return jsonify({"success": False, "message": "No payslips found matching the criteria"}), 404

    # Format the response with payslips data and pagination info
    response_data = []
    for payslip in payslips:
        payslip_data = {
            "payslipId": payslip.get("payslipId"),
            "employeeId": payslip.get("employeeId"),
            "month": payslip.get("month"),
            "year": payslip.get("year"),
            "lop_days": payslip.get("lop_days"),
            "generated_on": payslip.get("generated_on"),
            "filename": payslip.get("filename"),
            "download_link": f"/download/{payslip.get('payslipId')}",  # Link to download the payslip PDF
        }
        response_data.append(payslip_data)

    # Pagination metadata
    pagination = {
        "totalRecords": total_payslips,
        "currentPage": page,
        "totalPages": (total_payslips + page_size - 1) // page_size,  # Calculate total pages
    }

    return jsonify({
        "success": True,
        "payslips": response_data,
        "pagination": pagination,
    }), 200

@employee_bp.route('/viewpdf/<payslip_id>', methods=['GET'])
def view_payslip_pdf(payslip_id):
    # Retrieve the payslip information using the payslip_id from the database
    payslip = db.payslips.find_one({"payslipId": payslip_id})
    
    if not payslip:
        return jsonify({"success": False, "message": "Payslip not found"}), 404

    # Construct the file path for the PDF (assuming PDF files are stored on the server)
    file_path = os.path.join('path/to/salary/slips', payslip.get('filename'))

    if not os.path.exists(file_path):
        return jsonify({"success": False, "message": "Payslip PDF file not found"}), 404
    
    # Open and return the PDF file
    return send_file(
        file_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=payslip.get('filename')
    )