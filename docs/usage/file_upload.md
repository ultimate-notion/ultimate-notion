
# Uploading and importing files

Ultimate Notion provides comprehensive file upload functionality that allows
you to upload local files to Notion and import files from external URLs. You
can then use these uploaded files in various blocks like images, videos, PDFs,
and generic file blocks. Check out the list of [supported file types] for upload.

## Overview

Ultimate Notion supports two main methods for getting files into Notion:

1. **Local file upload** - Upload files from your local system to Notion
2. **External URL import** - Import files directly from external URLs

Both methods return an [UploadedFile] object that can be used in file-based blocks.

## Local File Upload

To upload a local file to Notion, use the `upload` method of a session:

```python
import ultimate_notion as uno

ROOT_PAGE = 'Tests'  # page with connected Ultimate Notion integration

notion = uno.Session.get_or_create()
root_page = notion.search_page(ROOT_PAGE).item()

# Upload a local file
with open('docs/assets/images/social-card.png', 'rb') as file:
    uploaded_image = notion.upload(file=file, file_name='social_card.png')

# Create a page and add the uploaded image
page = notion.create_page(parent=root_page, title='File Upload Demo')
page.append(uno.Image(uploaded_image, caption='An uploaded image'))
```

### File Size Limits and Multi-part Upload

Ultimate Notion automatically handles file size limitations and upload modes:

- **Single-part upload**: Files up to 20 MB are uploaded in a single request
- **Multi-part upload**: Files larger than 20 MB are automatically split into chunks and uploaded in multiple parts

!!! note

    Notion's free plan has a 5 MB file size limit. The 20 MB threshold is for paid plans.
    Ultimate Notion automatically detects the appropriate upload mode based on file size.

### File Name Detection

If you don't specify a `file_name`, Ultimate Notion will attempt to detect it from the file object:

```python
with open('LICENSE.txt', 'rb') as file:
    # File name 'LICENSE.txt' is automatically detected
    uploaded_file = notion.upload(file=file)
```

### MIME Type Detection

Ultimate Notion automatically detects MIME types for uploaded files using the `filetype` library. If the MIME type
cannot be determined, it defaults to `text/plain` since Notion doesn't support `application/octet-stream`.

## External URL Import

You can import files directly from external URLs without downloading them locally first:

```python
# Import a file from an external URL
url = ('https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/1080/'
       'Big_Buck_Bunny_1080_10s_20MB.mp4')
imported_file = notion.import_url(url=url, file_name='bunny.mp4')

page.append(uno.Video(imported_file, caption='Bunny movie 🐰'))
```

## External Files vs Uploaded Files

You can also work with external files without uploading them to Notion:

```python
# Create external file references
external_image = uno.url(
    'https://cdn.pixabay.com/photo/2019/08/06/09/16/flowers-4387827_1280.jpg'
)
external_pdf = uno.url(
    'https://www.melbpc.org.au/wp-content/uploads/2017/10/small-example-pdf-file.pdf',
    name='External Document'
)

page.append([
    uno.Image(external_image, caption='External image'),
    uno.PDF(external_pdf, caption='External PDF'),
])
```

!!! note

    External files are not stored in Notion and remain dependent on the external URL being accessible. Uploaded files
    are stored in Notion's infrastructure and remain available even if the original source is removed.

## File Upload Status and Expiry

### Upload Status Tracking

Uploaded files have a status that can be tracked using the [FileUploadStatus] enum:

- `PENDING` - File upload is in progress
- `UPLOADED` - File has been successfully uploaded and processed
- `EXPIRED` - File upload expired before completion
- `FAILED` - File upload failed

You can check the status of an uploaded file:

```python
print(f"Upload status: {uploaded_image.status}")
```

### Expiry Time Warning

!!! warning "File Upload Expiry"

    Uploaded files have an expiry time! Within this expiry period, the uploaded file **must be used**
    (e.g., added to a page or block), or it will be automatically deleted by Notion. You can check
    the expiry time using the `expiry_time` attribute:

    ```python
    print(f"File expires at: {uploaded_image.expiry_time}")
    ```

## Asynchronous File Import

### Non-blocking Import

The `import_url` method supports asynchronous operation. By default, it blocks until the import is complete,
but you can make it non-blocking:

```python
# Non-blocking import - returns immediately
video_file = notion.import_url(url=url, file_name='video.mp4', block=False)
print(f"Import started, status: {video_file.status}")  # Will likely be PENDING

# Later, check if the import is complete
video_file.update_status()
if video_file.status == uno.FileUploadStatus.UPLOADED:
    print("Import complete!")
else:
    print(f"Still processing... Status: {video_file.status}")
```

### Waiting for Completion

You can explicitly wait for an upload to complete:

```python
# Start non-blocking import
large_video = notion.import_url(url=url, file_name='large_video.mp4', block=False)

# Wait until upload is fully processed
large_video.wait_until_uploaded()
print("File is now ready to use!")

# Now you can safely use it in blocks
page.append(uno.Video(large_video, caption='Imported video'))
```

## Managing Uploads

### Listing Uploads

You can list all uploads in your workspace and filter by status:

```python
# List all uploads
all_uploads = notion.list_uploads()

# Filter by status
pending_uploads = notion.list_uploads(filter=uno.FileUploadStatus.PENDING)
completed_uploads = notion.list_uploads(filter=uno.FileUploadStatus.UPLOADED)
failed_uploads = notion.list_uploads(filter=uno.FileUploadStatus.FAILED)
```

### File Upload Information

Uploaded files provide detailed information:

```python
# Access file metadata
print(f"File name: {uploaded_image.file_name}")
print(f"Content type: {uploaded_image.content_type}")
print(f"Content length: {uploaded_image.content_length}")
print(f"Expiry time: {uploaded_image.expiry_time}")
print(f"Status: {uploaded_image.status}")

# Check import result for URL imports
if imported_file.file_import_result:
    print(f"Import result: {imported_file.file_import_result}")
```


## Complete Example

Here's a complete example demonstrating various file upload features including async operations:

``` py
--8<-- "examples/file_upload.py"
```

This example shows:

1. Creating a demo page
2. Uploading a local image file and checking its expiry time
3. Adding the uploaded image to a page with a caption
4. Importing a video from an external URL using non-blocking mode
5. Waiting for the import to complete and checking status
6. Adding the imported video to the page
7. Listing and filtering uploads by status

[UploadedFile]: ../../reference/ultimate_notion/file/#ultimate_notion.file.UploadedFile
[FileUploadStatus]: ../../reference/ultimate_notion/obj_api/enums/#ultimate_notion.obj_api.enums.FileUploadStatus
[supported file types]: https://developers.notion.com/docs/working-with-files-and-media#supported-file-types
