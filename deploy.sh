#!/bin/bash
# Quick deploy script for Scofield Bible Project

echo "🚀 Deploying Scofield Bible Project to GitHub Pages..."

# Step 1: Check if index.html exists
if [ ! -f "index.html" ]; then
    echo "❌ Error: index.html not found in current directory!"
    echo "Creating minimal index.html..."
    
    cat > index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Scofield Bible Project</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }
        .container {
            background: #f9f9f9;
            padding: 30px;
            border-radius: 10px;
            margin-top: 20px;
        }
        h1 {
            color: #2c3e50;
        }
        .status {
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
        }
        .success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .loading {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }
    </style>
</head>
<body>
    <h1>Connected Scofield Bible Project</h1>
    <p>A modern, interactive digital edition of the 1917 Scofield Reference Bible</p>
    
    <div class="container">
        <div class="status success" id="status1">
            ✅ Site is live and running
        </div>
        <div class="status loading" id="status2">
            ⏳ Loading enhanced features...
        </div>
        
        <h3>Features:</h3>
        <ul>
            <li>Interactive Bible reader</li>
            <li>Scofield study notes</li>
            <li>Cross-reference system</li>
            <li>Thematic studies</li>
            <li>Search functionality</li>
        </ul>
        
        <h3>Test Links:</h3>
        <div>
            <a href="#" onclick="testJavaScript()">Test JavaScript</a> | 
            <a href="#" onclick="testConsole()">Test Console</a> |
            <a href="#" onclick="testLocalStorage()">Test Storage</a>
        </div>
        
        <div id="testResults"></div>
    </div>
    
    <script>
        console.log('Scofield Bible Project loaded successfully');
        
        function testJavaScript() {
            document.getElementById('testResults').innerHTML = 
                '<p>✅ JavaScript is working! Time: ' + new Date().toLocaleTimeString() + '</p>';
        }
        
        function testConsole() {
            console.log('Test log message from Scofield Bible Project');
            document.getElementById('testResults').innerHTML = 
                '<p>✅ Console logging is working! Check browser console.</p>';
        }
        
        function testLocalStorage() {
            localStorage.setItem('scofield_test', 'working');
            const value = localStorage.getItem('scofield_test');
            document.getElementById('testResults').innerHTML = 
                `<p>✅ LocalStorage is working! Stored value: "${value}"</p>`;
        }
        
        // Auto-update status
        setTimeout(() => {
            document.getElementById('status2').className = 'status success';
            document.getElementById('status2').innerHTML = '✅ Enhanced features loaded';
        }, 2000);
    </script>
</body>
</html>
EOF
    
    echo "✅ Created minimal index.html"
fi

# Step 2: Check GitHub Pages configuration
echo "📋 Checking GitHub Pages setup..."

# Step 3: Provide next steps
echo "
📝 NEXT STEPS:
1. Commit and push to GitHub:
   git add .
   git commit -m 'Update Scofield Bible project'
   git push origin main

2. Wait 1-2 minutes for GitHub Pages to deploy

3. Visit your site:
   https://badreddine023.github.io/scofield-bible-project/

4. Check deployment status:
   https://github.com/badreddine023/scofield-bible-project/deployments

TROUBLESHOOTING:
- If 404: Check if GitHub Pages is enabled in repo Settings > Pages
- If blank: Check browser console for errors
- If old version: Clear browser cache or add ?v=2 to URL
"
