from flask import Flask, request, jsonify, render_template, send_file
import os
import asyncio
import subprocess
from test_headless import run_scraper  # your async scraper function

# Install Playwright Chromium if needed
def install_playwright_browsers():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except subprocess.CalledProcessError as e:
        print("Failed to install Playwright browsers:", e)

install_playwright_browsers()

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download')
def download_file():
    file_path = 'leads_with_company_details.csv'
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "No file available to download.", 404

@app.route('/start-scraping', methods=['POST'])
def start_scraping():
    data = request.get_json()
    session_cookie = data.get("sessionCookie")
    list_url = data.get("listUrl")

    if not session_cookie or not list_url:
        return jsonify({"message": "Missing input."}), 400

    try:
        asyncio.run(run_scraper(session_cookie, list_url))
        return jsonify({"message": "✅ Scraping completed successfully!"})
    except Exception as e:
        return jsonify({"message": f"❌ Scraping failed: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True)
