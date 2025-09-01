"""This example demonstrates how to upload files to Notion"""

import ultimate_notion as uno

PARENT_PAGE = 'Tests'  # Defines the page where the demo should be created


with uno.Session() as notion:
    parent = notion.search_page(PARENT_PAGE).item()
    # Create a new page for our file upload demo
    page = notion.create_page(parent=parent, title='File Upload Demo')

    with open('docs/assets/images/social-card.png', 'rb') as file:
        uploaded_image = notion.upload(file=file, file_name='social_card.png')

    # Add some introductory content and append the uploaded image.
    page.append(
        [
            uno.Heading1('File Upload Example'),
            uno.Image(
                uploaded_image, caption='An uploaded image used as a demo'
            ),
        ]
    )

    # Import an external file and append it to the page as video.
    url = (
        'https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/1080/'
        'Big_Buck_Bunny_1080_10s_20MB.mp4'
    )
    imported_file = notion.import_url(url=url, file_name='bunny.mp4')
    page.append(uno.Video(imported_file, caption='Bunny movie 🐰'))
