# Crowd Sense AI

**Crowd Sense AI** is an advanced, real-time people counting and crowd analysis system designed to monitor occupancy, analyze trends, and provide actionable insights. It leverages computer vision and deep learning technologies to detect and track individuals across multiple camera feeds.

## 🚀 Features

- **Real-Time People Counting**: Accurate detection and counting of individuals in video streams.
- **Zone-Based Monitoring**: Define custom zones within the camera feed to track specific areas (e.g., entrances, exits, queues).
- **Multi-Camera Support**: Manage and monitor multiple camera feeds simultaneously.
- **Analytics Dashboard**: Visual insights including hourly trends, peak occupancy intervals, and heatmaps.
- **Headless Mode**: Run detection in the background for efficiency.
- **Re-Identification (ReID)**: (Experimental) Track individuals across different cameras or timeframes.

## 🛠️ Tech Stack

- **Language**: Python 3.x
- **Computer Vision**: OpenCV, Ultralytics YOLO (Object Detection), Deep Sort (Tracking)
- **Backend**: Flask (Web Server), Flask-SQLAlchemy, Flask-JWT-Extended
- **Data Handling**: NumPy, Pandas (implied for analytics)
- **Frontend**: HTML5, CSS3, JavaScript (Dashboard)

## 📦 Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/RepalleLokeswar/Crowd-Sense-AI.git
    cd Crowd-Sense-AI
    ```

2.  **Create a Virtual Environment (Recommended)**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

##  ▶️ Usage

1.  **Start the Application**
    ```bash
    python app.py
    # OR
    python main.py
    ```

2.  **Access the Dashboard**
    Open your web browser and navigate to:
    `http://localhost:5000` (or the port specified in the console)

3.  **Configure System**
    - Go to the **Cameras** section to manage feeds.
    - Set up **Zones** to define monitoring areas.
    - View **Analytics** for reports.

## 📂 Project Structure

- `main.py`: Core detection loop and system logic.
- `app.py`: Flask application entry point.
- `camera_feed.py`, `detection.py`: Computer vision modules.
- `frontend/`: HTML/JS/CSS files for the user interface.
- `data/`: Storage for configs and models (Note: Large models are git-ignored).

## 📄 License
[MIT License](MIT%20LICENSE)
