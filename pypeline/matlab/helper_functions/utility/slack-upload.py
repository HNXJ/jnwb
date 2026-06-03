def slack_upload(IMAGE_TOKEN,channel_name,file_to_upload_path):

    import time
    from slack_sdk import WebClient
    client = WebClient(IMAGE_TOKEN)
    
    upload_and_then_share_file = client.files_upload(
        channels=channel_name,
        file=file_to_upload_path,
    )
    
    time.sleep(5)
    
    return

t = slack_upload(token,chan_name,chart_path)
