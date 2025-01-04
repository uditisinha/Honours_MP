import google.generativeai as genai
from sklearn.preprocessing import MinMaxScaler
import numpy as np
from typing import List, Dict
import os
from flask import Flask, render_template, url_for, request, redirect, session, flash
from datetime import datetime
import json
import re

GOOGLE_API_KEY='AIzaSyDmKGlt0wQREPzT8vI9WpzB5A37NuvLHlc'
GOOGLE_API_KEY='AIzaSyDwsOjC6diV88sDez5BuUeCYheVS0aa5UI'
# GOOGLE_API_KEY='AIzaSyBJXh--ktIhO3u6d_I51aTjo8brP6VwloU'

from models import db, User, UserResponse, Event, UserEvent, UserChats
def calculate_personality_similarity(user1_responses: Dict, user2_responses: Dict) -> tuple[float, str]:
    """
    Calculate personality similarity between two users and provide explanation
    Returns a tuple of (similarity_score, explanation)
    """
    genai.configure(api_key=GOOGLE_API_KEY)
    
    generation_config = {
        "temperature": 0,
        "top_p": 0.8,
        "top_k": 50,
        "max_output_tokens": 8192,
    }
    
    try:
        model = genai.GenerativeModel(
            model_name="gemini-pro",
            generation_config=generation_config
        )
        print("API configured successfully!")
    except Exception as e:
        print(f"Error: {e}")
    
    def clean_responses(responses: Dict) -> Dict:
        return {
            k: v for k, v in responses.items() 
            if k.startswith('q') and not k.startswith('_')
        }
    
    user1_clean = clean_responses(user1_responses)
    user2_clean = clean_responses(user2_responses)
    
    weights = {
        'q1_fictional_character': 0.15,
        'q2_friendship_value': 0.20,
        'q3_group_role': 0.15,
        'q4_adventurous_activity': 0.10,
        'q5_ultimate_day': 0.15,
        'q6_comfort_zone': 0.10,
        'q7_conversation_type': 0.15
    }
    
    try:
        prompt = f"""
        Compare these two sets of responses and analyze their compatibility:

        User 1:
        {json.dumps(user1_clean, indent=2)}

        User 2: 
        {json.dumps(user2_clean, indent=2)}

        Analyze the semantic similarity of responses considering:
        1. Direct matches in word choice/meaning
        2. Thematic alignment
        3. Compatible personality traits
        4. Similar values and preferences
        5. Complementary characteristics

        Return a JSON object with:
        1. Numeric scores for each question (0-1)
        2. A brief, personalized explanation (1 line) addressing both users directly about why they would or wouldn't be a good match

        Format:
        {{
            "scores": {{
                "q1_fictional_character": 0.85,
                "q2_friendship_value": 0.72,
                "q3_group_role": 0.93,
                "q4_adventurous_activity": 0.65,
                "q5_ultimate_day": 0.78,
                "q6_comfort_zone": 0.88,
                "q7_conversation_type": 0.70
            }},
            "explanation": "You two would be a great match because... [brief 2-3 line personalized explanation addressing both users]"
        }}
        """
        
        response = model.generate_content(prompt)
        
        json_match = re.search(r'\{[\s\S]*\}', response.text)
        if not json_match:
            raise ValueError("No JSON found in response")
        
        result = json.loads(json_match.group())
        scores = result['scores']
        explanation = result['explanation']
        
        weighted_score = sum(
            scores.get(q, 0) * weight
            for q, weight in weights.items()
        ) / sum(weights.values())

        return max(0.0, min(1.0, weighted_score)), explanation
        
    except Exception as e:
        print(f"Error calculating personality similarity: {str(e)}")
        return 0.5, "Unable to generate explanation due to error"
from typing import List, Dict
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime

def calculate_profile_similarity(current_user: User, other_users: List[User]) -> List[Dict]:
    """
    Calculate profile similarity scores between current user and other users
    with increased focus on shared interests and location.
    """
    if not other_users:
        return []
    
    similarity_scores = []
    
    for other_user in other_users:
        # Calculate interest similarity
        current_interests = set(current_user.interests)
        other_interests = set(other_user.interests)
        
        shared_interests = current_interests & other_interests
        total_interests = current_interests | other_interests
        
        # Calculate scores for different components
        interest_score = len(shared_interests) / len(total_interests) if total_interests else 0
        location_score = 0.0
        if other_user.city == current_user.city:
            location_score = 1.0
        elif other_user.country == current_user.country:
            location_score = 0.5
            
        # Age similarity (less weight)
        age_current = (datetime.now().date() - current_user.dob).days / 365.25
        age_other = (datetime.now().date() - other_user.dob).days / 365.25
        age_diff = abs(age_current - age_other)
        age_score = max(0, 1 - (age_diff / 10))  # Normalize age difference to 0-1 scale
        
        # Calculate final score with weights
        final_score = (
            interest_score * 0.7 +  # 70% weight to interests
            location_score * 0.2 +  # 20% weight to location
            age_score * 0.1        # 10% weight to age
        )
        
        # Build explanation
        location_match = ""
        if other_user.city == current_user.city:
            location_match = " and are in the same city"
        elif other_user.country == current_user.country:
            location_match = " and are in the same country"
        
        interest_percentage = (len(shared_interests) / len(total_interests) * 100) if total_interests else 0
        explanation = (f"You share {len(shared_interests)} interests: {', '.join(shared_interests)} "
                      f"({interest_percentage:.1f}% overlap){location_match}")
        
        # Debug information
        print(f"\nMatching details for {other_user.email}:")
        print(f"Shared interests: {shared_interests}")
        print(f"Interest score: {interest_score:.2f}")
        print(f"Location score: {location_score:.2f}")
        print(f"Age score: {age_score:.2f}")
        print(f"Final score: {final_score:.2f}")
        
        similarity_scores.append({
            "user": other_user,
            "score": float(final_score),
            "profile_explanation": explanation,
            "shared_interests": list(shared_interests)
        })
    
    return sorted(similarity_scores, key=lambda x: x["score"], reverse=True)


def get_combined_rankings(event_id: int, user_email: str) -> List[Dict]:
    """
    Get combined rankings with explanations for matches
    """
    event_users = User.query.join(UserEvent)\
        .filter(UserEvent.event_id == event_id)\
        .filter(User.email != user_email)\
        .all()
    
    current_user = User.query.filter_by(email=user_email).first()
    if not current_user:
        return []
    
    profile_scores = calculate_profile_similarity(current_user, event_users)
    personality_scores = []
    current_user_responses = UserResponse.query.filter_by(user_email=user_email).first()
    
    if current_user_responses:
        for other_user in event_users:
            other_user_responses = UserResponse.query.filter_by(user_email=other_user.email).first()
            if other_user_responses:
                personality_score, explanation = calculate_personality_similarity(
                    current_user_responses.__dict__,
                    other_user_responses.__dict__
                )
                personality_scores.append({
                    'user': other_user,
                    'score': personality_score,
                    'explanation': explanation
                })
    
    combined_scores = []
    for user in event_users:
        profile_score = next((s['score'] for s in profile_scores if s['user'].email == user.email), 0)
        personality_match = next((s for s in personality_scores if s['user'].email == user.email), 
                               {'score': 0, 'explanation': 'No personality data available. Please answer the personality questionnaire.'})
        
        combined_score = (profile_score * 0.4 + personality_match['score'] * 0.6)
        
        # Print detailed matching information to console
        print(f"\nMatch Analysis for {user.email}:")
        print(f"Profile Score: {profile_score:.2f}")
        print(f"Personality Score: {personality_match['score']:.2f}")
        print(f"Combined Score: {combined_score:.2f}")
        print(f"Explanation: {personality_match['explanation']}")
        print("-" * 80)
        
        combined_scores.append({
            'user': user,
            'score': combined_score,
            'profile_score': profile_score,
            'personality_score': personality_match['score'],
            'explanation': personality_match['explanation']
        })
    
    return sorted(combined_scores, key=lambda x: x['score'], reverse=True)


def update_ranked_matches_route(app):
    """
    Update the ranked_matches route to include personality-based matching
    """
    @app.route('/ranked_matches/<int:event_id>/', methods=['GET'])
    def rank_matches(event_id):
        if 'user' not in session:
            flash("Please log in to view matches.", 'warning')
            return redirect(url_for('login'))
        
        user_email = session['user']
        
        try:
            current_time = datetime.now()
            event = Event.query.get_or_404(event_id)
            
            # Check if event has expired
            if event.end_time <= current_time:
                # Clean up expired event data
                UserEvent.query.filter_by(event_id=event_id).delete()
                Event.query.filter_by(id=event_id).delete()
                db.session.commit()
                
                flash("This event has ended. The matches are no longer available.", 'info')
                return redirect(url_for('home'))
                
            is_participant = UserEvent.query.filter_by(
                user_email=user_email,  # Use the stored user_email variable
                event_id=event_id
            ).first() is not None
            is_host = event.host == user_email  # Use the stored user_email variable
            
            if not (is_participant or is_host):
                flash("You don't have access to these matches.", 'warning')
                return redirect(url_for('home'))
            
            user_responses = UserResponse.query.filter_by(user_email=user_email).first()
            if not user_responses:
                flash("Complete the personality questionnaire to get better matches!", 'warning')
            

            matches = get_combined_rankings(event_id, user_email)
            if not matches:
                flash("No matches available at this time.", 'info')
                return render_template('ranked_matches.html', matches=[])
            
            return render_template('ranked_matches.html', matches=matches)
            
        except Exception as e:
            app.logger.error(f"Error in rank_matches: {str(e)}")
            flash("An error occurred while retrieving matches. Please try again.", 'danger')
            return redirect(url_for('home'))