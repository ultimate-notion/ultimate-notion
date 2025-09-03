"""This example demonstrates how to upload files to Notion"""

import ultimate_notion as uno

PARENT_PAGE = 'Tests'  # Defines the page where the demo should be created


with uno.Session() as notion:
    parent = notion.search_page(PARENT_PAGE).item()
    # Create a new page for our file upload demo
    page = notion.create_page(parent=parent, title='File Upload Demo')

    with open('docs/assets/images/social-card.png', 'rb') as file:
        uploaded_image = notion.upload(file=file, file_name='social_card.png')

    # Check expiry time and status
    print(f'Uploaded image expires at: {uploaded_image.expiry_time}')
    print(f'Upload status: {uploaded_image.status}')

    # Add some introductory content and append the uploaded image.
    page.append(
        [
            uno.Heading1('File Upload Example'),
            uno.Image(
                uploaded_image, caption='An uploaded image used as a demo'
            ),
        ]
    )

    # Import an external file using non-blocking mode
    url = (
        'https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/1080/'
        'Big_Buck_Bunny_1080_10s_20MB.mp4'
    )
    imported_file = notion.import_url(
        url=url, file_name='bunny.mp4', block=False
    )
    print(f'Import started with status: {imported_file.status}')

    # Wait for the import to complete
    imported_file.wait_until_uploaded()
    print(f'Import completed with status: {imported_file.status}')

    page.append(uno.Video(imported_file, caption='Bunny movie 🐰'))

    # List uploads to see our files
    all_uploads = notion.list_uploads()
    print(f'Total uploads in workspace: {len(all_uploads)}')

    completed_uploads = notion.list_uploads(
        filter=uno.FileUploadStatus.UPLOADED
    )
    print(f'Completed uploads: {len(completed_uploads)}')
