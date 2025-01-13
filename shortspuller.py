import streamlit as st
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import pandas as pd
import html
import re

# Initialize YouTube API
@st.cache_data
def get_api_key():
    return st.secrets["youtube_api_key"]

def get_youtube_client():
    api_key = get_api_key()
    return build('youtube', 'v3', developerKey=api_key)

def get_channel_info(youtube, channel_id):
    """Get channel details including profile image and description"""
    request = youtube.channels().list(
        part="snippet,brandingSettings",
        id=channel_id
    )
    response = request.execute()
    
    if response['items']:
        channel = response['items'][0]['snippet']
        return {
            'name': channel['title'],
            'description': channel['description'],
            'profile_image': channel['thumbnails']['high']['url']
        }
    return None

def get_channel_id(youtube, channel_url):
    """Extract channel ID from URL and verify it exists"""
    if 'youtube.com/channel/' in channel_url:
        channel_id = channel_url.split('youtube.com/channel/')[1].split('/')[0]
    elif 'youtube.com/@' in channel_url:
        handle = channel_url.split('youtube.com/@')[1].split('/')[0]
        request = youtube.search().list(
            part="snippet",
            q=handle,
            type="channel",
            maxResults=1
        )
        response = request.execute()
        if response['items']:
            channel_id = response['items'][0]['snippet']['channelId']
        else:
            raise ValueError("Channel not found")
    else:
        raise ValueError("Invalid channel URL format")
    return channel_id

def extract_hashtags(text):
    """Extract hashtags from text"""
    hashtags = re.findall(r'#\w+', text)
    return ' '.join(hashtags)

def clean_text(text):
    """Clean text by removing HTML entities and special characters"""
    # First decode HTML entities
    text = html.unescape(text)
    # Remove any remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text

def get_recent_shorts(youtube, channel_id, max_results=50):
    """Get most recent Shorts from channel"""
    request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        maxResults=max_results,
        type="video",
        videoDuration="short"
    )
    return request.execute()

def get_transcript(video_id):
    """Get transcript for a video"""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return ' '.join(segment['text'] for segment in transcript)
    except:
        return "Transcript unavailable"

def main():
    st.title("ShortsPuller")
    
    # Input for channel URL and number of shorts
    col1, col2 = st.columns([3, 1])
    with col1:
        channel_url = st.text_input("Enter YouTube channel URL:")
    with col2:
        max_shorts = st.number_input("Number of Shorts", min_value=1, max_value=50, value=10)
    
    if channel_url:
        try:
            youtube = get_youtube_client()
            channel_id = get_channel_id(youtube, channel_url)
            
            # Get channel info
            channel_info = get_channel_info(youtube, channel_id)
            if channel_info:
                st.image(channel_info['profile_image'], width=100)
                st.write(f"Channel: {channel_info['name']}")
                with st.expander("Channel Description"):
                    st.write(channel_info['description'])
            
            # Create a progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()

            with st.spinner("Fetching Shorts list..."):
                shorts_response = get_recent_shorts(youtube, channel_id, max_shorts)
            
            total_shorts = len(shorts_response['items'])
            results = []
            
            for idx, item in enumerate(shorts_response['items']):
                # Update progress
                progress = int((idx + 1) * 100 / total_shorts)
                progress_bar.progress(progress)
                status_text.text(f"Processing video {idx + 1} of {total_shorts}...")
                
                video_id = item['id']['videoId']
                title_raw = item['snippet']['title']
                title = clean_text(title_raw)
                hashtags = extract_hashtags(title)
                title_without_hashtags = ' '.join(word for word in title.split() if not word.startswith('#'))
                
                transcript = get_transcript(video_id)
                
                results.append({
                    'Title': title_without_hashtags,
                    'Hashtags': hashtags,
                    'Video ID': video_id,
                    'URL': f'https://youtube.com/shorts/{video_id}',
                    'Transcript': clean_text(transcript),
                    'Channel Name': channel_info['name'] if channel_info else '',
                    'Channel Description': channel_info['description'] if channel_info else '',
                    'Channel Image URL': channel_info['profile_image'] if channel_info else ''
                })
            
            # Create DataFrame with just video data
            df = pd.DataFrame(results)[['Title', 'Hashtags', 'URL', 'Transcript']]

            # Get date range
            start_date = pd.to_datetime(shorts_response['items'][-1]['snippet']['publishedAt']).strftime('%B %d, %Y')
            end_date = pd.to_datetime(shorts_response['items'][0]['snippet']['publishedAt']).strftime('%B %d, %Y')
            
            # Display channel information in a nice format
            st.markdown("---")
            st.markdown("### Channel Information")
            col1, col2 = st.columns([1, 3])
            with col1:
                st.image(channel_info['profile_image'], width=100)
            with col2:
                st.markdown(f"**Channel Name:** {channel_info['name']}")
                st.markdown(f"**Date Range:** {start_date} - {end_date}")
                st.markdown(f"**Videos Analyzed:** {len(results)}")
                with st.expander("Channel Description"):
                    st.write(channel_info['description'])
            
            st.markdown("---")
            st.markdown("### Video Analysis")
            
            # Display the simplified DataFrame
            st.dataframe(df)
            
            # Create CSV with clean header format
            csv_content = f"""{channel_info['name']}
{start_date} - {end_date}
Latest {len(results)} shorts

{df.to_csv(index=False)}"""
            
            # Download button
            # Clean channel name for filename
            safe_channel_name = re.sub(r'[^\w\-_]', '_', channel_info['name'])
            filename = f"{safe_channel_name}_shorts_analysis.csv"
            
            st.download_button(
                "Download CSV",
                csv_content.encode('utf-8'),
                filename,
                "text/csv",
                key='download-csv'
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
