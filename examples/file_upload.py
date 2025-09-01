"""This example demonstrates how to upload files to Notion"""

import ultimate_notion as uno

PARENT_PAGE = 'Tests'  # Defines the page where the demo should be created


with uno.Session() as notion:
    parent = notion.search_page(PARENT_PAGE).item()
    # Create a new page for our file upload demo
    page = notion.create_page(parent=parent, title='File Upload Demo')

    with open('docs/assets/images/social-card.png', 'rb') as file:
        uploaded_image = notion.upload(file=file, name='Social Card Image')

    # Add some introductory content and use/process the uploaded image.
    page.append(
        [
            uno.Heading1('File Upload Example'),
            uno.Image(
                uploaded_image, caption='An uploaded image used as a demo'
            ),
        ]
    )
