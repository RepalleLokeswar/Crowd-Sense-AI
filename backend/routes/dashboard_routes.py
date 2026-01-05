from flask import Blueprint
from backend.controllers.dashboard_controller import DashboardController, get_commands, post_command

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/update_count', methods=['POST'])
def update_count():
    return DashboardController.update_counts()

@dashboard_bp.route('/get_count', methods=['GET'])
@dashboard_bp.route('/latest_stats', methods=['GET'])
def get_live_data():
    return DashboardController.get_live_data()

@dashboard_bp.route('/analytics/data', methods=['GET'])
def get_analytics():
    return DashboardController.get_analytics()

@dashboard_bp.route('/analytics/full_report', methods=['GET'])
def get_analytics_summary():
    return DashboardController.get_analytics_summary()

# Command Exchange
@dashboard_bp.route('/get_commands', methods=['GET'])
def get_cmds():
    return get_commands()

@dashboard_bp.route('/update_zones', methods=['POST']) # Used by camera editor for live update
def proxy_zones():
    return post_command()
