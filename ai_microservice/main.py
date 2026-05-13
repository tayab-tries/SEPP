import asyncio
import json
import logging
import websockets
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AI_Microservice")

async def handler(websocket):
    logger.info("Client connected to AI Microservice")
    try:
        async for message in websocket:
            data = json.loads(message)
            logger.info(f"Received command: {data}")
            
            # Example: Echo back a mock event
            if data.get("action") == "start_camera":
                await websocket.send(json.dumps({
                    "event": "camera_started",
                    "status": "ok"
                }))
                
                # Simulate an AI event later
                await asyncio.sleep(5)
                await websocket.send(json.dumps({
                    "event": "face_mismatch",
                    "severity": "critical",
                    "message": "Unrecognized face detected."
                }))
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("Client disconnected")

async def main():
    logger.info("Starting AI Microservice WebSocket server on ws://localhost:9001")
    async with websockets.serve(handler, "localhost", 9001):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down")
        sys.exit(0)
