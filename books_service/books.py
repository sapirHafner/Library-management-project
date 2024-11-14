from bson import ObjectId
from flask import Blueprint, Flask, jsonify, request
from flask_restful import Api
from pymongo import MongoClient
import requests
import ratings
import re

#from dotenv import load_dotenv


# Create a Blueprint for books
books = Blueprint('books', __name__)

# Establish MongoDB connection
client = MongoClient('mongodb://mongoDB:27017/')
db = client['library_db']
books_collection = db['books']



def get_all_books():
    all_books = list(books_collection.find({}, {'_id': False}))
    return jsonify(all_books), 200
    
def unvalid_field_content(request_data):
    # Check if genre is one of the accepted values
    accepted_genres = ["Fiction", "Children", "Biography", "Science", "Science Fiction", "Fantasy", "Other"]
    if request_data["genre"] not in accepted_genres:
        return "Genre is not one of the accepted values", 422
    
    # Check if ISBN is valid
    isbn = request_data["ISBN"]
    if isbn:
        if not isbn.isdigit() or len(isbn) != 13:
            return "ISBN must be a 13-digit number", 422

    # Check if publishedDate is valid
    published_date = request_data["publishedDate"]
    if published_date:
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', published_date):
            return "Published date must be in the form 'YYYY-MM-DD'", 422


#-----------------------------------------------------------------
# Route to handle books
@books.route('/books', methods=['GET'])
def handle_books():
    query_params = {}
    request_args = request.query_string.decode("utf-8")
    
    if not request_args:  # Checks if query_params is empty
        return get_all_books()
    else:
        if "&" in request_args:
            pairs = request_args.split("&")
            for pair in pairs:
                key, value = pair.split("=")
                value = value.replace("%20", " ")
                query_params[key.lower()] = value.lower().strip()
        else:
            query_params = {key.lower(): value.strip() for key, value in request.args.items()}

        filtered_books = apply_filters(query_params)
        if filtered_books:
            return jsonify(filtered_books), 200
        else:
            return "No books match the query parameters", 404

# Function to apply filters to books
def apply_filters(filters):
    field_mapping = {
        'title': 'title',
        'authors': 'authors',
        'isbn': 'ISBN',
        'genre': 'genre',
        'publisher': 'publisher',
        'publisheddate': 'publishedDate'
    }

    mongo_query = {}
    for field, value in filters.items():
        mapped_field = field_mapping.get(field, field)
        if mapped_field in ['authors', 'genre', 'publisher', 'title', 'ISBN']:
            mongo_query[mapped_field] = value
        elif mapped_field == 'publishedDate':
            mongo_query[mapped_field] = value.strip()

    filtered_books = list(books_collection.find(mongo_query, {'_id': False}))
    return filtered_books
#-----------------------------------------------------------------------------------------------


@books.route('/books', methods=['POST'])
def create_new_book():
    if not request.is_json:
        return jsonify({"error": "Unsupported media type. Only JSON format is supported."}), 415

    required_fields = ['title', 'ISBN', 'genre']
    for field in required_fields:
        if field not in request.json:
            return jsonify({"error": f"Missing '{field}' field in the request."}), 422

    validation_error = unvalid_field_content(request.get_json())
    if validation_error:
        return validation_error
    
    new_book = request.get_json()

    existing_isbn = books_collection.find_one({"ISBN": new_book['ISBN']})
    if existing_isbn:
        return jsonify({"error": "A book with the same ISBN already exists."}), 422

    # Fetch data from Google Books API
    google_books_url = f'https://www.googleapis.com/books/v1/volumes?q=isbn:{new_book["ISBN"]}'
    try:
        response = requests.get(google_books_url).json()
    except Exception as e:
        return jsonify({"error": f"Unable to connect to Google: {str(e)}"}), 500

    if 'items' not in response or len(response['items']) == 0:
        return jsonify({"error": "No items returned from Google Book API for given ISBN number"}), 400

    google_books_data = response['items'][0]['volumeInfo']
    authors_list = google_books_data.get("authors", ["missing"])
    if len(authors_list) == 0:
        authors_string = "missing"
    elif len(authors_list) == 1:
        authors_string = authors_list[0]
    else:
        authors_string = " and ".join(authors_list)
    
    new_book["authors"] = authors_string
    new_book["publisher"] = google_books_data.get("publisher", "missing")
    new_book["publishedDate"] = google_books_data.get("publishedDate", "missing")

    # Insert the new book record into the collection
    result = books_collection.insert_one(new_book)

    # Get the inserted document's _id
    inserted_id = result.inserted_id

    # Update the book record with the _id as the book ID
    books_collection.update_one({"_id": inserted_id}, {"$set": {"id": str(inserted_id)}})

    
    ratings.create_new_rating(str(inserted_id), new_book['title'])

    return jsonify({"id": str(inserted_id)}), 201



@books.route('/books/<string:id>', methods=['GET', 'PUT', 'DELETE'])
def handle_single_book(id):
    if request.method == 'GET':
        book = books_collection.find_one({"id": id}, {'_id': False})
        if book:
            return jsonify(book), 200
        else:
            return "Book not found", 404

    if request.method == 'DELETE':
        result = books_collection.delete_one({"id": id})
        if result.deleted_count == 1:
            ratings.delete_rating(id)
            return id, 200
        else:
            return "Book not found", 404
        
    if request.method == 'PUT':
        return handle_PUT_method(id)


def handle_PUT_method(id):
    if not request.is_json:  # Check if the request contains JSON data
        return "Unsupported media type. Only JSON data is accepted.", 415

    # Check if all required fields are present
    required_fields = ["title", "authors", "ISBN", "publisher", "publishedDate", "genre"]
    request_data = request.get_json()
    for field in required_fields:
        if field not in request_data:
            return f"Missing field: {field}", 422

    if unvalid_field_content(request_data) is not None:
        return unvalid_field_content(request_data)
    

    # Check if the book exists in the MongoDB collection
    book = books_collection.find_one({"_id": ObjectId(id)})
    if not book:
        return "Book not found", 404
    
    updated_data = {field: request_data[field] for field in request_data}

    # Perform the update operation
    result = books_collection.update_one({"_id": ObjectId(id)}, {"$set": updated_data})
    if result.modified_count == 1:
        
        ratings.update_rating_title(id, request_data["title"])
        return id, 200
    else:
        return "Failed to update the book", 500






