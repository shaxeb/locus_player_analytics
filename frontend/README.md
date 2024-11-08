# Player Analytics Dashboard

## Overview

The Player Analytics Dashboard is a web application designed to analyze and visualize player performance data collected from sensors. It provides insights into various metrics such as speed, steps, jumps, and acceleration magnitude over time. The application allows users to select a player, specify a time range, and view detailed analytics, including the ability to export the data as a CSV file.

## Features

- **Player Selection**: Choose a player from a list to analyze their performance data.
- **Time Range Selection**: Specify the start and end times for the analysis.
- **Real-time Progress Bar**: Visual feedback during data processing with an estimated time of arrival (ETA).
- **Data Visualization**: Graphs displaying acceleration magnitude and instantaneous speed over time.
- **Export Data**: Ability to export analyzed data as a CSV file for further analysis.

## Technologies Used

- **Frontend**: 
  - React
  - Material-UI
  - Charting Library (MUI X Charts)
  - Date Picker (MUI X Date Pickers)

- **Backend**: 
  - Flask
  - Numpy
  - MySQL
  - Numba (for performance optimization)

## Installation

### Prerequisites

- Python 3.x
- Node.js and npm
- MySQL Server

### Backend Setup

1. Clone the repository:
   ```
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```

4. Set up the MySQL database:
   - Create a database using the provided SQL script (`locusSportsDB.sql`).
   - Update the database connection settings in the `database_handler.py` file.

5. Run the backend server:
   ```
   python app.py
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install the required Node.js packages:
   ```
   npm install
   ```

3. Start the frontend development server:
   ```
   npm start
   ```

## Usage

1. Open your web browser and navigate to `http://localhost:3000` (or the port specified by your frontend server).
2. Select a player from the dropdown menu.
3. Choose the start and end times for the analysis.
4. Click the "Analyze" button to process the data.
5. View the results displayed on the dashboard, including graphs and metrics.
6. Use the "Export as CSV" button to download the analyzed data.

## Contributing

Contributions are welcome! If you have suggestions for improvements or new features, please open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Thanks to the contributors and the open-source community for their support and resources.
- Special thanks to the developers of the libraries and frameworks used in this project.
