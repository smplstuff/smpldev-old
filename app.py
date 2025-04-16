from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import json
import os
from datetime import datetime
import uuid
import requests
import hashlib
import secrets

# Create Flask app
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Secure secret key for sessions

# Database setup
def init_db():
    conn = sqlite3.connect('boltning.db')
    c = conn.cursor()
    
    # Create users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    
    # Create projects table with user_id foreign key and version field
    c.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            files TEXT NOT NULL,
            conversation TEXT NOT NULL,
            deployed INTEGER DEFAULT 0,
            deployment_name TEXT,
            version INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Helper function to hash passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Authentication routes
@app.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')

@app.route('/signup', methods=['GET'])
def signup_page():
    return render_template('signup.html')

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400
        
        # Check if username already exists
        conn = sqlite3.connect('boltning.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ?', (username,))
        existing_user = c.fetchone()
        
        if existing_user:
            conn.close()
            return jsonify({"error": "Username already exists"}), 400
        
        # Create new user
        user_id = str(uuid.uuid4())
        hashed_password = hash_password(password)
        created_at = datetime.now().isoformat()
        
        c.execute('INSERT INTO users (id, username, password, created_at) VALUES (?, ?, ?, ?)',
                 (user_id, username, hashed_password, created_at))
        conn.commit()
        conn.close()
        
        # Store user info in session
        session['user_id'] = user_id
        session['username'] = username
        
        return jsonify({"success": True, "user_id": user_id, "username": username})
    
    except Exception as e:
        print(f"Error in signup: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400
        
        # Verify credentials
        conn = sqlite3.connect('boltning.db')
        c = conn.cursor()
        c.execute('SELECT id, username, password FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()
        
        if not user or user[2] != hash_password(password):
            return jsonify({"error": "Invalid username or password"}), 401
        
        # Store user info in session
        session['user_id'] = user[0]
        session['username'] = user[1]
        
        return jsonify({"success": True, "user_id": user[0], "username": user[1]})
    
    except Exception as e:
        print(f"Error in login: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    if 'user_id' in session:
        return jsonify({
            "authenticated": True,
            "user_id": session['user_id'],
            "username": session['username']
        })
    else:
        return jsonify({"authenticated": False})

# Auth middleware for protected routes
def auth_required(route_function):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"error": "Authentication required"}), 401
            else:
                return redirect('/login')
        return route_function(*args, **kwargs)
    wrapper.__name__ = route_function.__name__
    return wrapper

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('index.html')

@app.route('/chat')
@auth_required
def chat():
    return render_template('chat.html')

# Deployment routes
@app.route('/p/<deployment_name>')
def view_deployment(deployment_name):
    try:
        conn = sqlite3.connect('boltning.db')
        c = conn.cursor()
        
        c.execute('SELECT files FROM projects WHERE deployment_name = ? AND deployed = 1', 
                 (deployment_name,))
        result = c.fetchone()
        conn.close()
        
        if not result:
            # Return a nice 404 page instead of plain text
            return render_template('deployment_not_found.html', deployment_name=deployment_name), 404
        
        files = json.loads(result[0])
        
        # Find the main HTML file
        html_file = next((f for f in files if f['filename'].endswith('.html')), None)
        
        if not html_file:
            return render_template('deployment_not_found.html', message="No HTML file found in deployment"), 404
        
        return html_file['content']
    
    except Exception as e:
        print(f"Error viewing deployment: {str(e)}")
        return render_template('deployment_not_found.html', message=f"Error: {str(e)}"), 500

@app.route('/api/generate', methods=['POST'])
@auth_required
def generate():
    try:
        # Get JSON data from request
        data = request.get_json()
        if not data:
            print("No JSON data received")
            return jsonify({"error": "No data provided"}), 400
            
        prompt = data.get('prompt', '')
        conversation = data.get('conversation', [])
        
        print(f"Received prompt: {prompt}")
        print(f"Conversation length: {len(conversation)}")
        
        # Format the conversation for the Pollinations API
        messages = []
        
        # Updated system message with more modern tech stack and features
        system_message = """You are an advanced AI specialized in generating modern, production-ready web applications. You create complete, responsive, and interactive websites using the latest web technologies and best practices:

KEY CAPABILITIES:
- Modern Frontend: React 18+, Vue 3, Svelte 4, Next.js 14, Nuxt 3, Astro 3.0
- Styling: 
  • Tailwind CSS with JIT compiler
  • CSS-in-JS (Styled Components, Emotion)
  • Modern CSS (Container Queries, Layers, Cascade Layers)
  • CSS Grid, Subgrid, and Advanced Flexbox
  • Variable Fonts & Font Loading Strategies
- Components & Design Systems:
  • Headless UI patterns
  • shadcn/ui, Radix UI
  • Custom hooks and composables
  • Micro-interactions & animations
- Full Stack Features:
  • tRPC/GraphQL APIs
  • Edge Functions & Middleware
  • Database integrations (Prisma, DrizzleORM)
  • Authentication flows (OAuth, Magic Links)
- Modern Architecture:
  • Islands Architecture
  • Partial Hydration
  • React Server Components
  • Edge Runtime Support
- Performance:
  • Core Web Vitals optimization
  • Image optimization & art direction
  • Resource hints & preloading
  • Bundle size optimization
- Developer Experience:
  • TypeScript with strict mode
  • ESLint & Prettier configuration
  • Git hooks & commit conventions
  • Testing setup (Vitest, Playwright)
- Advanced Features:
  • Real-time updates & WebSockets
  • Infinite scrolling & virtualization
  • Form validation & error handling
  • SEO & meta tag management
  • Dark mode with system preference
  • Responsive images & lazy loading
  • Touch gestures & interactions
  • Keyboard navigation & a11y
  • Error boundaries & fallbacks
  • Analytics & monitoring setup

I generate production-ready applications with proper:
- File structure & organization
- Component composition
- State management
- Error handling
- Loading states
- TypeScript types
- Documentation
- Best practices

RESPONSE FORMAT:
I always respond in this exact JSON structure:
{
  "files": [
    {
      "filename": "index.html",
      "type": "html",
      "content": "file contents"
    }
  ],
  "yapping": "Explanation of the project and its features"
}

Any explanations are ONLY included in the 'yapping' field. I never include explanations outside the JSON or in code blocks."""

        messages.append({
            "role": "system", 
            "content": system_message
        })
        
        # Add conversation messages
        for msg in conversation:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        print(f"Sending {len(messages)} messages to Pollinations API")
        
        # Call the Pollinations API
        model = data.get('model', 'openai')  # Default to OpenAI if not specified
        
        try:
            response = requests.post(
                'https://text.pollinations.ai',
                json={
                    "messages": messages,
                    "model": model,
                    "jsonMode": False,
                    "private": True
                },
                timeout=60
            )
            
            response.raise_for_status()
            result = response.text
            print(f"API response received successfully")
            
            # Return the plain text response
            return result
            
        except requests.exceptions.RequestException as req_err:
            print(f"API request error: {str(req_err)}")
            return jsonify({"error": f"API request failed: {str(req_err)}"}), 500
    
    except Exception as e:
        print(f"Error in /api/generate: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Updated project management endpoints using SQLite
@app.route('/api/projects/save', methods=['POST'])
@auth_required
def save_project():
    try:
        project_data = request.get_json()
        
        # Generate unique ID if not provided
        if 'id' not in project_data:
            project_data['id'] = str(uuid.uuid4())
        
        conn = sqlite3.connect('boltning.db')
        c = conn.cursor()
        
        # Convert dictionaries to JSON strings for storage
        files_json = json.dumps(project_data.get('files', []))
        conversation_json = json.dumps(project_data.get('conversation', []))
        
        # Check if this is an update to an existing project
        c.execute('SELECT * FROM projects WHERE id = ?', (project_data['id'],))
        existing = c.fetchone()
        
        if existing:
            # Get current version and increment it
            current_version = c.execute('SELECT version FROM projects WHERE id = ?', (project_data['id'],)).fetchone()[0]
            new_version = current_version + 1
            
            # Update existing project with new version
            c.execute('''
                UPDATE projects 
                SET name = ?, date = ?, files = ?, conversation = ?, version = ?
                WHERE id = ? AND user_id = ?
            ''', (
                project_data['name'],
                project_data.get('date', datetime.now().isoformat()),
                files_json,
                conversation_json,
                new_version,
                project_data['id'],
                session['user_id']
            ))
        else:
            # Insert new project with version 1
            c.execute('''
                INSERT INTO projects (id, user_id, name, date, files, conversation, deployed, deployment_name, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                project_data['id'],
                session['user_id'],
                project_data['name'],
                project_data.get('date', datetime.now().isoformat()),
                files_json,
                conversation_json,
                0,  # Not deployed by default
                None,  # No deployment name until deployed
                1  # Initial version
            ))
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "id": project_data['id']})
    
    except Exception as e:
        print(f"Error saving project: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/projects/list', methods=['GET'])
@auth_required
def list_projects():
    try:
        conn = sqlite3.connect('boltning.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT id, name, date, deployed, deployment_name, version 
            FROM projects 
            WHERE user_id = ? 
            ORDER BY date DESC
        ''', (session['user_id'],))
        
        projects = [
            {
                "id": row[0],
                "name": row[1],
                "date": row[2],
                "deployed": bool(row[3]),
                "deployment_name": row[4],
                "version": row[5]
            }
            for row in c.fetchall()
        ]
        
        conn.close()
        
        return jsonify(projects)
    
    except Exception as e:
        print(f"Error listing projects: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/projects/<project_id>', methods=['GET'])
@auth_required
def get_project(project_id):
    try:
        conn = sqlite3.connect('boltning.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT * FROM projects 
            WHERE id = ? AND user_id = ?
        ''', (project_id, session['user_id']))
        
        row = c.fetchone()
        
        if not row:
            return jsonify({"error": "Project not found"}), 404
        
        project = {
            "id": row[0],
            "user_id": row[1],
            "name": row[2],
            "date": row[3],
            "files": json.loads(row[4]),
            "conversation": json.loads(row[5]),
            "deployed": bool(row[6]),
            "deployment_name": row[7],
            "version": row[8] if len(row) > 8 else 1
        }
        
        conn.close()
        
        return jsonify(project)
    
    except Exception as e:
        print(f"Error getting project {project_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/projects/<project_id>', methods=['DELETE'])
@auth_required
def delete_project(project_id):
    try:
        conn = sqlite3.connect('boltning.db')
        c = conn.cursor()
        
        c.execute('''
            DELETE FROM projects 
            WHERE id = ? AND user_id = ?
        ''', (project_id, session['user_id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True})
    
    except Exception as e:
        print(f"Error deleting project {project_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/projects/deploy', methods=['POST'])
@auth_required
def deploy_project():
    try:
        data = request.get_json()
        project_id = data.get('project_id')
        deployment_name = data.get('deployment_name')
        
        if not project_id or not deployment_name:
            return jsonify({"error": "Project ID and deployment name are required"}), 400
        
        # Check if deployment name is available
        conn = sqlite3.connect('boltning.db')
        c = conn.cursor()
        
        c.execute('SELECT id FROM projects WHERE deployment_name = ? AND deployed = 1', (deployment_name,))
        existing = c.fetchone()
        
        if existing and existing[0] != project_id:
            conn.close()
            return jsonify({"error": "Deployment name is already taken"}), 400
        
        # Update the project as deployed
        c.execute('''
            UPDATE projects 
            SET deployed = 1, deployment_name = ? 
            WHERE id = ? AND user_id = ?
        ''', (deployment_name, project_id, session['user_id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True, 
            "deployment_url": f"/p/{deployment_name}"
        })
    
    except Exception as e:
        print(f"Error deploying project: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/projects/undeploy', methods=['POST'])
@auth_required
def undeploy_project():
    try:
        data = request.get_json()
        project_id = data.get('project_id')
        
        if not project_id:
            return jsonify({"error": "Project ID is required"}), 400
        
        conn = sqlite3.connect('boltning.db')
        c = conn.cursor()
        
        c.execute('''
            UPDATE projects 
            SET deployed = 0, deployment_name = NULL 
            WHERE id = ? AND user_id = ?
        ''', (project_id, session['user_id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True})
    
    except Exception as e:
        print(f"Error undeploying project: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
