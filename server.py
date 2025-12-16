#!/usr/bin/env python3
"""
MyTune Backend Server
Flask API for YouTube music search and stream URL extraction
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import yt_dlp
import re
from typing import Dict, List, Optional
import logging

app = Flask(__name__)
CORS(app)  # Enable CORS for Android app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class YouTubeService:
    """Service for YouTube operations"""
    
    def __init__(self):
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage', 'configs'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            }
        }
    
    def search(self, query: str, max_results: int = 20) -> List[Dict]:
        """
        Search YouTube for music
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            List of track dictionaries
        """
        try:
            search_opts = {
                **self.ydl_opts,
                'extract_flat': True,
                'default_search': 'ytsearch',
            }
            
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                search_query = f"ytsearch{max_results}:{query}"
                result = ydl.extract_info(search_query, download=False)
                
                if not result or 'entries' not in result:
                    return []
                
                tracks = []
                for entry in result['entries']:
                    if entry:
                        track = self._format_track(entry)
                        if track:
                            tracks.append(track)
                
                return tracks
                
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def get_stream_url(self, video_id: str) -> Optional[Dict]:
        """
        Get audio stream URL for a video
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Dictionary with stream URL and metadata
        """
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                # Get best audio format
                formats = info.get('formats', [])
                audio_format = None
                
                # Prefer m4a audio
                for fmt in formats:
                    if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                        audio_format = fmt
                        break
                
                if not audio_format and formats:
                    audio_format = formats[0]
                
                if not audio_format:
                    return None
                
                return {
                    'streamUrl': audio_format.get('url'),
                    'title': info.get('title', 'Unknown'),
                    'artist': info.get('artist') or info.get('uploader', 'Unknown Artist'),
                    'duration': info.get('duration', 0),
                    'thumbnail': self._get_best_thumbnail(info.get('thumbnails', [])),
                    'videoId': video_id
                }
                
        except Exception as e:
            logger.error(f"Stream URL error: {e}")
            return None
    
    def _format_track(self, entry: Dict) -> Optional[Dict]:
        """Format YouTube entry to track dictionary"""
        try:
            video_id = entry.get('id')
            if not video_id:
                return None
            
            title = entry.get('title', 'Unknown')
            
            # Try to extract artist from title
            artist = 'Unknown Artist'
            if ' - ' in title:
                parts = title.split(' - ', 1)
                artist = parts[0].strip()
                title = parts[1].strip()
            elif entry.get('uploader'):
                artist = entry.get('uploader')
            
            return {
                'id': video_id,
                'title': title,
                'artist': artist,
                'duration': entry.get('duration', 0),
                'thumbnail': self._get_best_thumbnail(entry.get('thumbnails', [])),
                'videoId': video_id
            }
            
        except Exception as e:
            logger.error(f"Format track error: {e}")
            return None
    
    def _get_best_thumbnail(self, thumbnails: List[Dict]) -> str:
        """Get best quality thumbnail URL"""
        if not thumbnails:
            return ''
        
        # Sort by resolution
        sorted_thumbs = sorted(
            thumbnails,
            key=lambda x: (x.get('width', 0) * x.get('height', 0)),
            reverse=True
        )
        
        return sorted_thumbs[0].get('url', '') if sorted_thumbs else ''


# Initialize service
youtube_service = YouTubeService()


@app.route('/api/search', methods=['GET'])
def search():
    """
    Search for music on YouTube
    
    Query params:
        q: Search query
        limit: Max results (default: 20)
    """
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 20))
    
    if not query:
        return jsonify({'error': 'Query parameter required'}), 400
    
    logger.info(f"Search request: {query}")
    
    results = youtube_service.search(query, limit)
    
    return jsonify({
        'results': results,
        'count': len(results)
    })


@app.route('/api/stream/<video_id>', methods=['GET'])
def get_stream(video_id: str):
    """
    Get stream URL for a video
    
    Path params:
        video_id: YouTube video ID
    """
    logger.info(f"Stream request: {video_id}")
    
    stream_data = youtube_service.get_stream_url(video_id)
    
    if not stream_data:
        return jsonify({'error': 'Failed to get stream URL'}), 404
    
    return jsonify(stream_data)


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'MyTune Backend'})


@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'name': 'MyTune Backend API',
        'version': '1.0.0',
        'endpoints': {
            'search': '/api/search?q=query&limit=20',
            'stream': '/api/stream/<video_id>',
            'health': '/api/health'
        }
    })


if __name__ == '__main__':
    logger.info("Starting MyTune Backend Server...")
    logger.info("Server running on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
