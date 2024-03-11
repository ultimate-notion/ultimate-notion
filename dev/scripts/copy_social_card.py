"""Override the default social card image as we are using a custom image for the social card."""

import os
import shutil


def on_post_build(config, **kwargs):
    if os.path.exists('assets/images/socialg'):
        shutil.copyfile('docs/assets/images/social-card.png', 'assets/images/social/index.png')
