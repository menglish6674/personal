#----Requirements----
#You will need to install Python on the machine that this will run
#Install Flask: pip install flask pyodbc
#Ensure ODBC Driver 18 for SQL Server is installed
#@Author: Mike English (michael.english@hcl-software.com)
#@Version: 1.7 (Dynamic Login + Days Filter + CSV Export)
#-----------------------------------------------------------------

import os
import webbrowser
import threading
from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for
import pyodbc

app = Flask(__name__)
# A static secret key ensures sessions aren't invalidated if the Flask server restarts
app.secret_key = 'change-this-to-a-secure-random-string-in-production' 

# --- SQL CONFIGURATION (Defaults) ---
SQL_CONFIG = {
    'database': 'BFEnterprise',
    'driver': '{ODBC Driver 18 for SQL Server}'
}

def get_db_connection(server, user=None, password=None, use_win_auth=False):
    if use_win_auth:
        conn_str = (
            f"DRIVER={SQL_CONFIG['driver']};"
            f"SERVER={server};"
            f"DATABASE={SQL_CONFIG['database']};"
            "Trusted_Connection=yes;"
            "Encrypt=yes;"
            "TrustServerCertificate=yes;"
        )
    else:
        conn_str = (
            f"DRIVER={SQL_CONFIG['driver']};"
            f"SERVER={server};"
            f"DATABASE={SQL_CONFIG['database']};"
            f"UID={user};"
            f"PWD={password};"
            "Encrypt=yes;"
            "TrustServerCertificate=yes;"
        )
    return pyodbc.connect(conn_str)

# --- ROUTES ---

@app.after_request
def add_header(response):
    # Prevent the browser from caching the dashboard or login pages
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        server = request.form.get('server')
        use_win_auth = request.form.get('win_auth') == 'on'
        user = request.form.get('username') if not use_win_auth else 'Windows Authentication (Host Account)'
        password = request.form.get('password') if not use_win_auth else None
        
        try:
            # Test the connection with provided credentials and server
            conn = get_db_connection(server, user, password, use_win_auth)
            conn.close()
            
            # If successful, store connection info in the session
            session['db_server'] = server
            session['db_user'] = user
            session['db_password'] = password
            session['use_win_auth'] = use_win_auth
            
            return redirect(url_for('index'))
        except Exception as e:
            error = "Authentication failed. Check your server name, credentials, or permissions."
            print(f"Login failed: {str(e)}")
            
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.route('/logout')
def logout():
    session.pop('db_server', None)
    session.pop('db_user', None)
    session.pop('db_password', None)
    session.pop('use_win_auth', None)
    session.clear()  
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'db_user' not in session or 'db_server' not in session:
        return redirect(url_for('login'))
    return render_template_string(HTML_TEMPLATE, username=session['db_user'], server=session['db_server'])

@app.route('/api/deleted-actions')
def get_actions():
    if 'db_user' not in session or 'db_server' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = None
    try:
        # Get the 'days' parameter from the URL, defaulting to 2
        days_lookback = request.args.get('days', default=2, type=int)
        if days_lookback < 1: 
            days_lookback = 1

        conn = get_db_connection(
            session.get('db_server'),
            session.get('db_user'), 
            session.get('db_password'), 
            session.get('use_win_auth', False)
        )
        cursor = conn.cursor()
        
        # We use a parameterized query (?) to safely inject the days into DATEADD
        query = """
            SELECT 
                A.ID, 
                A.ParentID,
                A.Name, 
                A.Username,
                A.CreationTime,
                CONVERT(VARCHAR(MAX), CONVERT(VARBINARY(MAX), A.Fields)) AS Script
            FROM [BFEnterprise].[dbo].[ACTION_DEFS] A
            JOIN [BFEnterprise].[dbo].[ACTION_FLAGS] F ON A.ID = F.ActionID
            WHERE F.IsDeleted = 1
              AND A.CreationTime >= DATEADD(day, ?, GETDATE())
              AND A.ParentID != 0
            ORDER BY A.CreationTime DESC
        """
        # Pass the negative value of days_lookback to go backwards in time
        cursor.execute(query, (-days_lookback,))
        rows = cursor.fetchall()
        
        actions = []
        for row in rows:
            actions.append({
                'id': row[0],
                'parent_id': row[1] if row[1] else "None", 
                'name': row[2],
                'issuer': row[3],
                'date': row[4].strftime('%Y-%m-%d %H:%M:%S') if row[4] else "N/A",
                'script': row[5] if row[5] else "No script found in database blob."
            })
        
        return jsonify(actions)
    except Exception as e:
        print(f"SQL Error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()

# --- HTML TEMPLATES ---

LOGIN_TEMPLATE = r"""
<!DOCTYPE html>
<html>
<head>
    <title>Login - BigFix Forensics</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; margin: 0; background: #f8f9fa; display: flex; align-items: center; justify-content: center; height: 100vh; }
        .login-container { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 320px; }
        h2 { color: #0078d4; margin-top: 0; text-align: center; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; font-size: 14px; color: #333; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        
        .checkbox-group { display: flex; align-items: center; margin-bottom: 20px; margin-top: 20px; }
        .checkbox-group input { margin-right: 10px; cursor: pointer; }
        .checkbox-group label { margin-bottom: 0; font-weight: normal; cursor: pointer; }
        
        .login-btn { width: 100%; padding: 10px; background: #0078d4; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; margin-top: 5px; }
        .login-btn:hover { background: #005a9e; }
        .error { color: #d13438; font-size: 13px; margin-bottom: 15px; text-align: center; padding: 10px; background: #fde7e9; border-radius: 4px; }
        .bf-logo { width: 100px; display: block; margin: 0 auto 20px auto; }
        .disabled-input { background-color: #f1f1f1; cursor: not-allowed; }
    </style>
    <script>
        function toggleAuthMode() {
            var isWinAuth = document.getElementById('win_auth').checked;
            var userInput = document.getElementById('username');
            var passInput = document.getElementById('password');
            
            if (isWinAuth) {
                userInput.disabled = true;
                passInput.disabled = true;
                userInput.classList.add('disabled-input');
                passInput.classList.add('disabled-input');
                userInput.required = false;
                passInput.required = false;
            } else {
                userInput.disabled = false;
                passInput.disabled = false;
                userInput.classList.remove('disabled-input');
                passInput.classList.remove('disabled-input');
                userInput.required = true;
                passInput.required = true;
            }
        }
    </script>
</head>
<body>
    <div class="login-container">
        <img src="https://help.hcl-software.com/bigfix/landing/images/bf-logo.svg" alt="BigFix Logo" class="bf-logo">
        <h2>Database Login</h2>
        {% if error %}
            <div class="error">{{ error }}</div>
        {% endif %}
        <form method="POST">
            
            <div class="form-group">
                <label for="server">SQL Server Name / IP</label>
                <input type="text" id="server" name="server" placeholder="e.g. 10.0.0.5 or SERVER\SQLEXPRESS" required>
            </div>
            
            <div class="checkbox-group">
                <input type="checkbox" id="win_auth" name="win_auth" onchange="toggleAuthMode()">
                <label for="win_auth">Use Windows Authentication</label>
            </div>
            
            <div class="form-group">
                <label for="username">SQL Username</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">SQL Password</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <button type="submit" class="login-btn">Connect</button>
        </form>
    </div>
</body>
</html>
"""

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html>
<head>
    <title>BigFix Forensics</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; margin: 40px; background: #f8f9fa; }
        .container { 
            max-width: 1200px; 
            margin: auto; 
            background: white; 
            padding: 25px; 
            border-radius: 8px; 
            box-shadow: 0 4px 10px rgba(0,0,0,0.1); 
            position: relative; 
        }
        
        .header-brand {
            position: absolute;
            top: 20px;
            right: 25px;
            text-align: right;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            pointer-events: none; 
        }
        
        .auth-bar {
            pointer-events: auto; 
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 15px;
            background: #f1f8ff;
            padding: 8px 15px;
            border-radius: 20px;
            border: 1px solid #e1ecf4;
        }

        .logo-container {
            display: flex;
            align-items: center; 
            gap: 15px; 
        }

        .bf-logo { width: 120px; height: auto; }
        .ps-text { font-size: 13px; font-weight: bold; color: #605e5c; letter-spacing: 0.5px; text-transform: uppercase; text-align: right; line-height: 1.2; }

        h1 { color: #0078d4; border-bottom: 2px solid #f1f1f1; padding-bottom: 10px; margin-top: 0; padding-right: 350px; }
        
        .toolbar { margin-bottom: 20px; position: relative; z-index: 50; display: flex; gap: 15px; align-items: center; }
        .refresh-btn { padding: 8px 20px; background: #0078d4; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .refresh-btn:hover { background: #005a9e; }
        
        .export-btn { padding: 8px 20px; background: #107c41; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .export-btn:hover { background: #0b5a2f; }
        
        select { padding: 8px; border-radius: 4px; border: 1px solid #ccc; font-family: inherit; }
        
        .logout-btn { padding: 6px 15px; background: #d13438; color: white; text-decoration: none; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 13px; display: inline-block; }
        .logout-btn:hover { background: #a80000; }
        
        table { width: 100%; border-collapse: collapse; table-layout: fixed; position: relative; z-index: 10; }
        th { background: #f4f4f4; color: #333; padding: 12px; text-align: left; border-bottom: 2px solid #ddd; }
        td { padding: 12px; border-bottom: 1px solid #eee; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        tr:hover { background: #f1f8ff; }
        
        .details { margin-top: 30px; display: none; padding: 20px; border-top: 3px solid #0078d4; background: #fafafa; border-radius: 0 0 5px 5px; }
        pre { background: #2d2d2d; color: #fff; padding: 15px; border-radius: 5px; overflow-x: auto; white-space: pre-wrap; font-family: 'Consolas', monospace; font-size: 13px; line-height: 1.5; }
        .meta-info { margin-bottom: 15px; font-size: 14px; color: #555; }
    </style>
</head>
<body>
    <div class="container">
        
        <div class="header-brand">
            <div class="auth-bar">
                <span style="color: #555; font-size: 13px;">Server: <strong>{{ server }}</strong> | User: <strong>{{ username }}</strong></span>
                <a href="/logout" class="logout-btn">Logout</a>
            </div>
            
            <div class="logo-container">
                <div class="ps-text">BigFix<br>Professional Services</div>
                <img src="https://help.hcl-software.com/bigfix/landing/images/bf-logo.svg" alt="BigFix Logo" class="bf-logo">
            </div>
        </div>

        <h1>Deleted BigFix Actions Forensic Audit</h1>
        <br>
        
        <div class="toolbar">
            <div>
                <label for="daysFilter" style="font-weight: bold; color: #333; margin-right: 5px;">Look back:</label>
                <select id="daysFilter">
                    <option value="1">1 Day</option>
                    <option value="2" selected>2 Days</option>
                    <option value="7">7 Days</option>
                    <option value="14">14 Days</option>
                    <option value="30">30 Days</option>
                    <option value="90">90 Days</option>
                    <option value="365">1 Year</option>
                </select>
            </div>
            <button class="refresh-btn" onclick="loadActions()">Refresh Data</button>
            <button class="export-btn" onclick="exportToCSV()">Export to CSV</button>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th style="width: 12%">Action ID</th>
                    <th style="width: 12%">Parent ID</th>
                    <th style="width: 36%">Action Name</th>
                    <th style="width: 20%">Operator</th>
                    <th style="width: 20%">Issue Date</th>
                </tr>
            </thead>
            <tbody id="tableBody">
                <tr><td colspan="5" style="text-align:center;">Click Refresh to load data...</td></tr>
            </tbody>
        </table>

        <div id="detailsArea" class="details">
            <h2 style="margin-top:0;">Action Detail: <span id="dispId"></span></h2>
            <div class="meta-info">
                <strong>Parent Action ID:</strong> <span id="dispParentId"></span><br>
                <strong>Issued By:</strong> <span id="dispIssuer"></span><br>
                <strong>Date:</strong> <span id="dispDate"></span>
            </div>
            <pre id="dispScript"></pre>
        </div>
    </div>

    <script>
        let currentActionData = []; // Store the fetched data globally for the CSV export

        async function loadActions() {
            try {
                const days = document.getElementById('daysFilter').value;
                const response = await fetch(`/api/deleted-actions?days=${days}`);
                
                if (response.status === 401) {
                    window.location.href = '/login';
                    return;
                }
                
                const data = await response.json();
                currentActionData = data; // Save to global variable
                
                const body = document.getElementById('tableBody');
                body.innerHTML = '';
                
                if (data.length === 0) {
                    body.innerHTML = `<tr><td colspan="5" style="text-align:center;">No deleted actions found (Last ${days} Days).</td></tr>`;
                    return;
                }

                data.forEach(action => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `<td>${action.id}</td>
                                    <td>${action.parent_id}</td>
                                    <td>${action.name}</td>
                                    <td>${action.issuer}</td>
                                    <td>${action.date}</td>`;
                    tr.onclick = function() { showDetails(action); };
                    body.appendChild(tr);
                });
            } catch (err) {
                alert("Error loading data. Check console for details.");
                console.error("Fetch error:", err);
            }
        }

        function showDetails(action) {
            document.getElementById('detailsArea').style.display = 'block';
            document.getElementById('dispId').innerText = action.id;
            document.getElementById('dispParentId').innerText = action.parent_id;
            document.getElementById('dispIssuer').innerText = action.issuer;
            document.getElementById('dispDate').innerText = action.date;
            document.getElementById('dispScript').textContent = action.script;
            document.getElementById('detailsArea').scrollIntoView({ behavior: 'smooth' });
        }

        function exportToCSV() {
            if (!currentActionData || currentActionData.length === 0) {
                alert("No data available to export. Please load data first.");
                return;
            }

            // Define CSV headers
            let csvContent = "Action ID,Parent ID,Action Name,Operator,Issue Date\n";

            // Loop through data and append rows
            currentActionData.forEach(row => {
                // Safely format strings to prevent issues with commas or quotes inside the text
                let id = row.id;
                let parent = row.parent_id;
                let name = `"${(row.name || "").replace(/"/g, '""')}"`;
                let issuer = `"${(row.issuer || "").replace(/"/g, '""')}"`;
                let date = row.date;

                csvContent += `${id},${parent},${name},${issuer},${date}\n`;
            });

            // Create a Blob and trigger the download
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            
            link.setAttribute("href", url);
            link.setAttribute("download", `BigFix_Deleted_Actions_${new Date().toISOString().slice(0,10)}.csv`);
            link.style.visibility = 'hidden';
            
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        window.onload = loadActions;
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    port = 5757
    url = f"http://localhost:{port}"
    
    print(f"Starting Web Server. Automatically opening {url}...")
    
    # Run the browser launch on a slight delay to ensure the Flask server is ready
    threading.Timer(1.25, lambda: webbrowser.open(url)).start()
    
    app.run(debug=False, port=port)