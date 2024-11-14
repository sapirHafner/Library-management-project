from flask import Blueprint, Flask, jsonify, request
from pymongo import MongoClient
import requests

loans = Blueprint('loans', __name__)

# Establish MongoDB connection
client = MongoClient('mongodb://mongoDB:27017/')
db = client['library_db']
loans_collection = db['loans']



def get_all_loans():
    all_loans = list(loans_collection.find({}, {'_id': False}))
    return jsonify(all_loans), 200


@loans.route('/loans', methods=['GET'])
def handle_loans():
    query_params = {key: value.strip() for key, value in request.args.items()}
    if not query_params:
        return get_all_loans()

    filtered_loans = apply_filters(loans_collection.find({}, {'_id': False}), query_params)
    if filtered_loans:
        return jsonify(filtered_loans), 200
    else:
        return "No loans match the query parameters", 404

def apply_filters(loans, filters):
    field_mapping = {
        'membername': 'memberName',
        'isbn': 'ISBN',
        'bookid': 'bookID',
        'loanid': 'loanID',
        'title': 'title',
        'loandate': 'loanDate'
    }

    for field, value in filters.items():
        mapped_field = field_mapping.get(field, field)
        if mapped_field in ['memberName', 'bookID', 'loanID', 'title', 'ISBN']:
            loans = [loan for loan in loans if value.lower() == loan.get(mapped_field, '').lower()]
        elif mapped_field == 'loanDate':
            loans = [loan for loan in loans if value == loan.get('loanDate', '').strip()]

    return list(loans)



@loans.route('/loans', methods=['POST'])
def create_new_loan():
    if not request.is_json:
        return jsonify({"error": "Unsupported media type. Only JSON format is supported."}), 415
    
    required_fields = ['memberName', 'ISBN', 'loanDate']
    for field in required_fields:
        if field not in request.json:
            return jsonify({"error": f"Missing '{field}' field in the request."}), 422
        
    new_loan_request = request.get_json()

    # Check if the member already has 2 or more books on loan
    member_loans_count = loans_collection.count_documents({"memberName": new_loan_request['memberName']})
    if member_loans_count >= 2:
        return jsonify({"error": "Member already has 2 or more books on loan"}), 422

    # Check if the book is already on loan
    book_on_loan = loans_collection.find_one({"ISBN": new_loan_request['ISBN']})
    if book_on_loan:
        return jsonify({"error": "Book is already on loan"}), 422

    # Retrieve the book details from the books service
    try:
        response = requests.get(f'http://books:5001/books?isbn={new_loan_request["ISBN"]}')
        response.raise_for_status()
        book_data = response.json()
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Unable to connect to Books Service: {str(e)}"}), 500

    if not book_data:
        return jsonify({"error": "Book with the given ISBN not found"}), 422

    book_info = book_data[0]
    
    # Create a new loan record
    new_loan = {
        "memberName": new_loan_request['memberName'],
        "ISBN": new_loan_request['ISBN'],
        "title": book_info['title'],
        "bookID": book_info['id'],
        "loanDate": new_loan_request['loanDate']
    }
    # Insert the new loan record into the collection
    result = loans_collection.insert_one(new_loan)

    # Get the inserted document's _id
    inserted_id = result.inserted_id

    # Update the loanID field with the inserted _id
    new_loan['loanID'] = str(inserted_id)

    # Update the document with the loanID field
    loans_collection.update_one({"_id": inserted_id}, {"$set": {"loanID": new_loan['loanID']}})

    return jsonify({"id": new_loan["loanID"]}), 201 




@loans.route('/loans/<string:loanID>', methods=['GET', 'DELETE'])
def handle_single_loan(loanID):
    if request.method == 'GET':
        loan = loans_collection.find_one({"loanID": loanID}, {'_id': False})
        if loan:
            return jsonify(loan), 200
        else:
            return "Loan not found", 404

    if request.method == 'DELETE':
        result = loans_collection.delete_one({"loanID": loanID})
        if result.deleted_count == 1:
            return loanID, 200
        else:
            return "Loan not found", 404
        


