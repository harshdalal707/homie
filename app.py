"""
AI Booking Assistant Backend - With Confirmation Flow
Version 3.1.0
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import random
import re
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from enum import Enum
import uuid
import sys
import os

# Add the path to import from the original file
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
CORS(app)

# Import all the classes and data from the original app_advanced.py
# For simplicity, I'll include the essential parts here

# ==================== CONFIGURATION ====================

class Config:
    """Application configuration"""
    DEBUG = True
    HOST = '0.0.0.0'
    PORT = 5000
    BASE_PRICES = {
        'cleaning': 500,
        'plumbing': 800,
        'electrical': 700,
        'painting': 1200,
        'carpentry': 1000,
        'pest_control': 1500,
        'ac_repair': 900,
        'gardening': 600,
        'appliance_repair': 850
    }
    URGENCY_MULTIPLIERS = {
        'urgent': 1.5,
        'normal': 1.0,
        'low': 0.85
    }
    AREA_MULTIPLIERS = {
        'whole_house': 3.0,
        'large': 1.5,
        'medium': 1.2,
        'small': 1.0
    }

class Priority(str, Enum):
    URGENT = "Urgent"
    NORMAL = "Normal"
    LOW = "Low"

class BookingStatus(str, Enum):
    PENDING = "Pending"
    CONFIRMED = "Confirmed"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"

@dataclass
class Helper:
    id: str
    name: str
    rating: float
    specialty: str
    availability: str
    completed_jobs: int
    years_experience: int
    phone: str = None

@dataclass
class BookingPreview:
    """Preview of a booking before confirmation"""
    service: str
    service_key: str
    area: str
    priority: str
    helper: Dict
    eta: str
    price_estimate: str
    additional_notes: Optional[str]
    suggestions: List[str]

# Simple in-memory storage
bookings = []
booking_counter = 1000
pending_previews = {}  # Store previews by session ID

# Helper database (simplified version)
helpers_db = {
    'cleaning': [
        Helper('H001', 'Raj Kumar', 4.8, 'Deep Cleaning', 'Available', 245, 5, '+91-9876543210'),
        Helper('H002', 'Priya Sharma', 4.9, 'Kitchen Specialist', 'Available', 312, 7, '+91-9876543211'),
        Helper('H003', 'Sunita Devi', 4.9, 'Sanitization', 'Available', 278, 6, '+91-9876543213'),
    ],
    'plumbing': [
        Helper('H005', 'Suresh Yadav', 4.9, 'Pipe Expert', 'Available', 456, 10, '+91-9876543214'),
        Helper('H006', 'Vijay Patil', 4.6, 'Bathroom Fitting', 'Available', 198, 5, '+91-9876543215'),
    ],
    'electrical': [
        Helper('H009', 'Ramesh Gupta', 4.9, 'Wiring Specialist', 'Available', 523, 12, '+91-9876543218'),
        Helper('H010', 'Sanjay Verma', 4.7, 'Appliance Repair', 'Available', 289, 7, '+91-9876543219'),
    ],
    'painting': [
        Helper('H013', 'Mukesh Kumar', 4.8, 'Interior Designer', 'Available', 167, 8, '+91-9876543222'),
    ],
    'carpentry': [
        Helper('H016', 'Ravi Das', 4.9, 'Furniture Expert', 'Available', 389, 11, '+91-9876543225'),
    ],
    'pest_control': [
        Helper('H019', 'Dinesh Patel', 4.8, 'Rodent Control', 'Available', 312, 7, '+91-9876543228'),
    ],
    'ac_repair': [
        Helper('H022', 'Prakash Yadav', 4.9, 'AC Installation', 'Available', 445, 10, '+91-9876543231'),
    ],
    'gardening': [
        Helper('H025', 'Krishna Das', 4.8, 'Lawn Specialist', 'Available', 234, 6, '+91-9876543234'),
    ],
    'appliance_repair': [
        Helper('H027', 'Arjun Patel', 4.8, 'Washing Machine', 'Available', 289, 7, '+91-9876543236'),
    ]
}

# ==================== MESSAGE PARSER ====================

class MessageParser:
    SERVICE_KEYWORDS = {
        'cleaning': ['clean', 'safai', 'sweep', 'mop', 'dust', 'vacuum', 'wash'],
        'plumbing': ['plumb', 'pipe', 'leak', 'tap', 'faucet', 'drain', 'water', 'toilet'],
        'electrical': ['electric', 'wiring', 'switch', 'socket', 'light', 'fan', 'power'],
        'painting': ['paint', 'color', 'wall', 'ceiling', 'whitewash'],
        'carpentry': ['carpenter', 'wood', 'furniture', 'door', 'window'],
        'pest_control': ['pest', 'rat', 'cockroach', 'insect', 'termite'],
        'ac_repair': ['ac', 'air condition', 'cooling'],
        'gardening': ['garden', 'lawn', 'plant'],
        'appliance_repair': ['washing machine', 'fridge', 'microwave', 'appliance']
    }
    
    AREA_KEYWORDS = {
        'kitchen': ['kitchen', 'rasoi'],
        'bedroom': ['bedroom', 'room'],
        'bathroom': ['bathroom', 'toilet'],
        'living_room': ['living room', 'hall'],
        'whole_house': ['whole house', 'entire home', 'full house', 'pura ghar']
    }
    
    URGENCY_HIGH = ['urgent', 'jaldi', 'asap', 'emergency', 'immediately', 'now']
    URGENCY_LOW = ['later', 'whenever', 'flexible', 'no rush']
    
    @classmethod
    def extract_service(cls, message: str) -> Tuple[str, str]:
        msg_lower = message.lower()
        for service_key, keywords in cls.SERVICE_KEYWORDS.items():
            if any(keyword in msg_lower for keyword in keywords):
                return service_key, service_key.replace('_', ' ').title() + " Service"
        return 'cleaning', 'General Service'
    
    @classmethod
    def extract_area(cls, message: str) -> Tuple[str, str]:
        msg_lower = message.lower()
        for area_key, keywords in cls.AREA_KEYWORDS.items():
            if any(keyword in msg_lower for keyword in keywords):
                area_name = area_key.replace('_', ' ').title()
                if area_key == 'whole_house':
                    return area_name, 'whole_house'
                elif any(word in msg_lower for word in ['big', 'large']):
                    return area_name, 'large'
                elif any(word in msg_lower for word in ['small']):
                    return area_name, 'small'
                else:
                    return area_name, 'medium'
        return 'Home', 'medium'
    
    @classmethod
    def extract_urgency(cls, message: str) -> str:
        msg_lower = message.lower()
        if any(word in msg_lower for word in cls.URGENCY_HIGH):
            return Priority.URGENT.value
        elif any(word in msg_lower for word in cls.URGENCY_LOW):
            return Priority.LOW.value
        return Priority.NORMAL.value

# ==================== BOOKING ENGINE ====================

class BookingEngine:
    @staticmethod
    def calculate_eta(urgency: str) -> str:
        base_times = {
            Priority.URGENT.value: random.randint(10, 20),
            Priority.NORMAL.value: random.randint(30, 60),
            Priority.LOW.value: random.randint(120, 240)
        }
        eta_minutes = base_times.get(urgency, 30)
        if eta_minutes < 60:
            return f"{eta_minutes} minutes"
        else:
            hours = eta_minutes // 60
            return f"{hours} hour{'s' if hours > 1 else ''}"
    
    @staticmethod
    def calculate_price(service_key: str, area_size: str, urgency: str) -> int:
        base_price = Config.BASE_PRICES.get(service_key, 500)
        area_mult = Config.AREA_MULTIPLIERS.get(area_size, 1.0)
        urgency_key = urgency.lower()
        urgency_mult = Config.URGENCY_MULTIPLIERS.get(urgency_key, 1.0)
        final_price = int(base_price * area_mult * urgency_mult)
        return round(final_price / 50) * 50
    
    @staticmethod
    def select_helper(service_key: str, urgency: str) -> Helper:
        helpers = helpers_db.get(service_key, helpers_db['cleaning'])
        available = [h for h in helpers if h.availability == 'Available']
        if not available:
            available = helpers
        if urgency == Priority.URGENT.value:
            return max(available, key=lambda h: h.rating)
        return random.choice(available)
    
    @staticmethod
    def get_suggestions(service_key: str, current_priority: str, current_price: int) -> List[str]:
        """Generate helpful suggestions"""
        suggestions = []
        
        # Priority suggestions
        if current_priority == Priority.NORMAL.value:
            urgent_price = int(current_price * 1.5)
            low_price = int(current_price * 0.85)
            suggestions.append(f"💡 Need it faster? Upgrade to Urgent for ₹{urgent_price} (ETA: 10-20 min)")
            suggestions.append(f"💡 Save money? Choose Low priority for ₹{low_price}")
        elif current_priority == Priority.URGENT.value:
            normal_price = int(current_price / 1.5)
            suggestions.append(f"💡 Not urgent? Save ₹{current_price - normal_price} with Normal priority")
        
        # Helper suggestions
        helpers = helpers_db.get(service_key, [])
        if len(helpers) > 1:
            suggestions.append(f"💡 We have {len(helpers)} helpers available - we'll assign the best match")
        
        return suggestions

# ==================== API ROUTES ====================

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "service": "AI Booking Assistant API (With Confirmation)",
        "version": "3.1.0",
        "endpoints": {
            "POST /chat/preview": "Preview booking from message",
            "POST /chat/confirm": "Confirm previewed booking",
            "POST /chat/modify": "Modify booking details",
            "GET /bookings": "Get all bookings"
        },
        "total_bookings": len(bookings)
    })

@app.route("/chat/preview", methods=["POST"])
def preview_booking():
    """Preview a booking without confirming it"""
    try:
        data = request.json
        message = data.get("message", "").strip()
        user_id = data.get("user_id", str(uuid.uuid4()))
        
        if not message:
            return jsonify({"error": "Message required"}), 400
        
        # Parse message
        service_key, service_name = MessageParser.extract_service(message)
        area_name, area_size = MessageParser.extract_area(message)
        urgency = MessageParser.extract_urgency(message)
        
        # Calculate details
        eta = BookingEngine.calculate_eta(urgency)
        price = BookingEngine.calculate_price(service_key, area_size, urgency)
        helper = BookingEngine.select_helper(service_key, urgency)
        suggestions = BookingEngine.get_suggestions(service_key, urgency, price)
        
        # Create preview
        preview = {
            "service": service_name,
            "service_key": service_key,
            "area": area_name,
            "area_size": area_size,
            "priority": urgency,
            "helper": {
                'id': helper.id,
                'name': helper.name,
                'rating': helper.rating,
                'specialty': helper.specialty,
                'phone': helper.phone,
                'experience': f"{helper.years_experience} years",
                'completed_jobs': helper.completed_jobs
            },
            "eta": eta,
            "price_estimate": f"₹{price}",
            "price_value": price,
            "suggestions": suggestions,
            "user_id": user_id
        }
        
        # Store preview for this session
        session_id = str(uuid.uuid4())
        pending_previews[session_id] = preview
        preview["session_id"] = session_id
        
        return jsonify({
            "type": "preview",
            "preview": preview
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error in /chat/preview: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/chat/confirm", methods=["POST"])
def confirm_booking():
    """Confirm and create a booking"""
    try:
        global booking_counter
        data = request.json
        session_id = data.get("session_id")
        
        if not session_id or session_id not in pending_previews:
            return jsonify({"error": "Invalid or expired session"}), 400
        
        preview = pending_previews[session_id]
        
        # Create actual booking
        booking_counter += 1
        booking = {
            "booking_id": f"BK{booking_counter}",
            "user_id": preview["user_id"],
            "service": preview["service"],
            "service_key": preview["service_key"],
            "area": preview["area"],
            "priority": preview["priority"],
            "helper": preview["helper"],
            "eta": preview["eta"],
            "status": "Confirmed",
            "price_estimate": preview["price_estimate"],
            "created_at": datetime.now().isoformat()
        }
        
        bookings.append(booking)
        
        # Remove from pending
        del pending_previews[session_id]
        
        return jsonify({
            "type": "confirmed",
            "message": "🎉 Booking confirmed successfully!",
            "booking": booking
        }), 201
        
    except Exception as e:
        app.logger.error(f"Error in /chat/confirm: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/chat/modify", methods=["POST"])
def modify_booking():
    """Modify a preview based on user request"""
    try:
        data = request.json
        session_id = data.get("session_id")
        modification = data.get("modification", "").strip().lower()
        
        if not session_id or session_id not in pending_previews:
            return jsonify({"error": "Invalid session"}), 400
        
        preview = pending_previews[session_id]
        service_key = preview["service_key"]
        area_size = preview.get("area_size", "medium")
        
        # Apply modifications
        if any(word in modification for word in ["urgent", "jaldi", "fast"]):
            preview["priority"] = Priority.URGENT.value
            preview["eta"] = BookingEngine.calculate_eta(Priority.URGENT.value)
            price = BookingEngine.calculate_price(service_key, area_size, Priority.URGENT.value)
            preview["price_estimate"] = f"₹{price}"
            preview["price_value"] = price
            
        elif any(word in modification for word in ["later", "low", "flexible"]):
            preview["priority"] = Priority.LOW.value
            preview["eta"] = BookingEngine.calculate_eta(Priority.LOW.value)
            price = BookingEngine.calculate_price(service_key, area_size, Priority.LOW.value)
            preview["price_estimate"] = f"₹{price}"
            preview["price_value"] = price
        
        # Change helper
        if "helper" in modification or "different" in modification:
            helper = BookingEngine.select_helper(service_key, preview["priority"])
            preview["helper"] = {
                'id': helper.id,
                'name': helper.name,
                'rating': helper.rating,
                'specialty': helper.specialty,
                'phone': helper.phone,
                'experience': f"{helper.years_experience} years",
                'completed_jobs': helper.completed_jobs
            }
        
        # Update suggestions
        preview["suggestions"] = BookingEngine.get_suggestions(
            service_key, preview["priority"], preview["price_value"]
        )
        
        pending_previews[session_id] = preview
        
        return jsonify({
            "type": "preview",
            "message": "Updated your booking details:",
            "preview": preview
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error in /chat/modify: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/bookings", methods=["GET"])
def get_bookings():
    return jsonify({
        "total": len(bookings),
        "bookings": bookings
    }), 200

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 AI BOOKING ASSISTANT - CONFIRMATION FLOW")
    print("=" * 60)
    print(f"📍 Server: http://{Config.HOST}:{Config.PORT}")
    print("\n📚 New Endpoints:")
    print("   - POST /chat/preview    Preview booking")
    print("   - POST /chat/confirm    Confirm booking")
    print("   - POST /chat/modify     Modify preview")
    print("\n✅ Ready with confirmation flow!")
    print("=" * 60)
    print()
    
    app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)