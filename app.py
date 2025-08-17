#!/usr/bin/env python3
"""
FastAPI server for KellerBot - integrates message generation with GroupMe interaction.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import json
import os
import uvicorn
from server.bot_controller import BotController
from env import BOT_GROUP_ID

app = FastAPI(title="KellerBot API", description="Async bot controller for GroupMe integration")

# Initialize bot controller
try:
    bot_controller = BotController(BOT_GROUP_ID)
    print("✅ Bot controller initialized successfully")
except Exception as e:
    print(f"⚠️ Warning: Bot controller initialization failed: {e}")
    print("📱 Server will start but bot functionality will be limited")
    bot_controller = None

# Setup templates
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
async def startup():
    """Start the bot polling when the app starts."""
    # Start bot initialization in background to not block server startup
    asyncio.create_task(startup_bot())

async def startup_bot():
    """Start the bot polling in the background."""
    try:
        # Wait a moment for the server to fully start
        await asyncio.sleep(2)
        print("🚀 Starting bot initialization...")
        
        # Check if bot controller is available
        if bot_controller is None:
            print("⚠️ Bot controller not available, skipping bot startup")
            return
        
        # Check environment variables
        if not BOT_GROUP_ID:
            print("⚠️ Warning: BOT_GROUP_ID not set - bot will not be able to send messages")
        if not os.getenv('GROUPME_ACCESS_TOKEN'):
            print("⚠️ Warning: GROUPME_ACCESS_TOKEN not set - bot will not be able to access GroupMe")
        if not os.getenv('OPENAI_API_KEY'):
            print("⚠️ Warning: OPENAI_API_KEY not set - message generation will fail")
        
        await bot_controller.start_polling()
        print("✅ Bot polling started automatically on app startup")
    except Exception as e:
        print(f"⚠️ Warning: Bot polling failed to start: {e}")
        print("📱 Server will continue running, but bot functionality may be limited")
        print("🔧 Check your GroupMe credentials and configuration")

@app.on_event("shutdown")
async def shutdown():
    """Stop the bot polling when the app shuts down."""
    try:
        await bot_controller.stop_polling()
        print("🛑 Bot polling stopped on app shutdown")
    except Exception as e:
        print(f"⚠️ Failed to stop bot polling on shutdown: {e}")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "bot_controller": "available" if bot_controller is not None else "unavailable",
        "timestamp": asyncio.get_event_loop().time()
    }

@app.get("/api/status")
async def get_status():
    """Get bot status."""
    if bot_controller is None:
        raise HTTPException(status_code=503, detail="Bot controller not available - check configuration")
    return await bot_controller.get_bot_status()

@app.get("/api/messages")
async def get_messages():
    """Get pending messages."""
    return await bot_controller.get_pending_messages()

@app.get("/api/config")
async def get_config():
    """Get current configuration."""
    return await bot_controller.get_config()

@app.post("/api/config")
async def update_config(request: Request):
    """Update configuration."""
    try:
        new_config = await request.json()
        await bot_controller.update_config(new_config)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"success": False, "error": str(e)})

@app.post("/api/messages/{message_id}/select")
async def select_message(message_id: str, request: Request):
    """Select a message option."""
    try:
        data = await request.json()
        option_index = data.get('option_index', 0)
        success = await bot_controller.select_message_option(message_id, option_index)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"success": False, "error": str(e)})

@app.post("/api/messages/{message_id}/send")
async def send_message(message_id: str):
    """Send a selected message."""
    try:
        success = await bot_controller.send_selected_message(message_id)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"success": False, "error": str(e)})

@app.post("/api/messages/{message_id}/delete")
async def delete_message(message_id: str):
    """Delete a message."""
    try:
        await bot_controller.delete_message(message_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"success": False, "error": str(e)})

@app.post("/api/generate/introduction")
async def generate_introduction():
    """Generate an introduction message."""
    try:
        message = await bot_controller.generate_introduction()
        return {"success": True, "message": message}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"success": False, "error": str(e)})

@app.post("/api/generate/test")
async def generate_test_message():
    """Generate a test message."""
    try:
        message = await bot_controller.generate_test_message()
        return {"success": True, "message": message}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"success": False, "error": str(e)})



@app.post("/api/bot/server")
async def set_bot_server(request: Request):
    """Set the bot server group ID."""
    try:
        data = await request.json()
        group_id = data.get('group_id')
        if not group_id:
            raise HTTPException(status_code=400, detail={"success": False, "error": "Group ID is required"})
        
        await bot_controller.set_bot_server(group_id)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"success": False, "error": str(e)})

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Run the FastAPI app with uvicorn
    try:
        uvicorn.run(
            app,  # Pass app object directly when not using reload
            host="0.0.0.0", 
            port=8080, 
            log_level="info"
        )
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        exit(1)
