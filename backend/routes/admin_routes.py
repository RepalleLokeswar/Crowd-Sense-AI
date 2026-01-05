from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from backend.controllers.admin_controller import AdminController

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/auth/signup', methods=['POST'])
def signup():
    return AdminController.signup()

@admin_bp.route('/auth/login', methods=['POST'])
def login():
    return AdminController.login()

@admin_bp.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    return AdminController.get_profile(get_jwt_identity())

@admin_bp.route('/system/start', methods=['POST'])
@jwt_required()
def start_system():
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return jsonify({'msg': 'Admins only!'}), 403
    return AdminController.start_system(get_jwt_identity())

@admin_bp.route('/system/stop', methods=['POST'])
@jwt_required()
def stop_system():
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return jsonify({'msg': 'Admins only!'}), 403
    return AdminController.stop_system(get_jwt_identity())

@admin_bp.route('/system/status', methods=['GET'])
@jwt_required()
def system_status():
    return AdminController.get_system_status(get_jwt_identity())

@admin_bp.route('/zones', methods=['GET'])
@jwt_required()
def get_zones():
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return jsonify({'msg': 'Admins only!'}), 403
    return AdminController.get_zones(get_jwt_identity())

@admin_bp.route('/zones/config', methods=['POST'])
@jwt_required()
def update_zones_config():
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return jsonify({'msg': 'Admins only!'}), 403
    return AdminController.update_zones_config(get_jwt_identity())

@admin_bp.route('/export', methods=['GET'])
@jwt_required()
def export_data():
    return AdminController.export_data(get_jwt_identity())

@admin_bp.route('/alerts', methods=['GET'])
@jwt_required()
def get_alerts():
    return AdminController.get_alerts(get_jwt_identity())

@admin_bp.route('/logs', methods=['GET'])
@jwt_required()
def get_logs():
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return jsonify({'msg': 'Admins only!'}), 403
    return AdminController.get_logs(get_jwt_identity())
