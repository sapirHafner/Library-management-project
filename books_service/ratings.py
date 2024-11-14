from flask import Blueprint, request, jsonify
from pymongo import MongoClient, DESCENDING
from bson import ObjectId

client = MongoClient('mongodb://mongoDB:27017/')
db = client['library_db']
ratings_collection = db['ratings']

def create_new_rating(id, title):
    """
    Creates a new rating entry with the given id and title.
    Initially, the values array will be empty, and the average will be 0.
    """
    new_rating = {
        '_id' : id,
        'id': id,
        'title': title,
        'values': [],
        'average': 0.0
    }
    ratings_collection.insert_one(new_rating)

    # Remove the _id field from the dictionary before returning
    new_rating_without_id = new_rating.copy()
    new_rating_without_id.pop('_id')

    return new_rating_without_id


def delete_rating(id):
    result = ratings_collection.delete_one({'id': id})
    if result.deleted_count > 0:
        return id, 200
    return "Rating not found", 404


def update_rating_title(id, new_title):
    """
    Updates the title of the rating document with the given ID.
    """
    result = ratings_collection.update_one({'id': id}, {'$set': {'title': new_title}})
    if result.matched_count > 0:
        return f"Title of id={id} updated successfully", 200
    return "Book not found", 404

# Create a Blueprint for ratings
ratings = Blueprint('ratings', __name__)


@ratings.route('/ratings', methods=['GET'])
def get_ratings():
    query_id = request.args.get('id')
    if query_id:
        rating = ratings_collection.find_one({'id': query_id})
        if rating:
            rating['_id'] = str(rating['_id'])  # Convert ObjectId to string for JSON serialization
            return jsonify(rating), 200
        else:
            return jsonify({'error': 'Rating not found'}), 404
    ratings = list(ratings_collection.find())
    for rating in ratings:
        rating['_id'] = str(rating['_id'])  # Convert ObjectId to string for JSON serialization
    return jsonify(ratings), 200


@ratings.route('/ratings/<id>', methods=['GET'])
def get_rating_by_id(id):
    rating = ratings_collection.find_one({'id': id})
    if rating:
        rating['_id'] = str(rating['_id'])  # Convert ObjectId to string for JSON serialization
        return jsonify(rating), 200
    return "error : Rating not found", 404


@ratings.route('/ratings/<id>/values', methods=['POST'])
def add_rating(id):
    if request.content_type != 'application/json':
        return jsonify({'error': 'Unsupported media type'}), 415

    data = request.get_json(silent=True)
    if not data or 'value' not in data:
        return jsonify({'error': 'Unprocessable Content: Missing field or incorrect field name'}), 422

    if not isinstance(data['value'], int) or not 1 <= data['value'] <= 5:
        return jsonify({'error': 'Unprocessable Content: Value must be an integer between 1 and 5'}), 422

    rating = ratings_collection.find_one({'id': id})
    if rating:
        new_values = rating['values'] + [data['value']]
        new_average = round(sum(new_values) / len(new_values), 2)
        ratings_collection.update_one(
            {'id': id},
            {'$set': {'values': new_values, 'average': new_average}}
        )
        return jsonify({'id': id}), 201
    else:
        return "error: Book not found", 404


@ratings.route('/top', methods=['GET'])
def get_top_books():
    # Step 1: Fetch all books with at least 3 ratings
    valid_ratings = list(ratings_collection.find({'values.2': {'$exists': True}}))
    
    # Step 2: Sort the books by their average rating in descending order
    valid_ratings.sort(key=lambda x: x['average'], reverse=True)
    
    # Step 3: Identify the top 3 scores
    if not valid_ratings:
        return jsonify({'top': []}), 200
    
    top_books = []
    top_scores = set()
    
    for rating in valid_ratings:
        if len(top_scores) < 3:
            top_books.append(rating)
            top_scores.add(rating['average'])
        elif rating['average'] in top_scores:
            top_books.append(rating)
        else:
            break

    # Step 4: Format the response
    top_books_response = [
        {'id': book['id'], 'title': book['title'], 'average': book['average']}
        for book in top_books
    ]

    return jsonify({'top': top_books_response}), 200