import shutil
import subprocess
from pathlib import PosixPath
from PIL import Image, UnidentifiedImageError
from tempfile import TemporaryDirectory

def create_image_variant(target: PosixPath, size: (int, int), source: str):
    """
       Generate requested image and write to target

        :param target: Path to write image string
        :param size: (Width, Height)
        :param source: Image directory string

    """


    # Create.py looked for source image file, but it did not exist
    # Therefore, we need to construct that file from whatever resources are available: Other resource should be in app's src/app/resources/*

    try:
        # Get the largest available image
        image = find_largest_png(PosixPath(source).parent)

        #test_split = str(target).split('.')
        # Determine the image type needed
        image_type = str(target).split('.')[-1]

        if image_type == 'icns':
            image = create_icns(target, image)  # Will create temp img artifacts, then write icns file

        else: # Create a single image

            if size is not None:
                image = image.resize(size)

            # # Make sure the target directory exists
            target.parent.mkdir(parents=True, exist_ok=True)

            image.save(source)  # Image file saved, so it is now available... or should I use temp here too?
            source_img_file = source  # Source created, and therefore now available

            # Copy the source image to the target location
            shutil.copy(source_img_file, target)

    except Exception:
        import sys
        the_type, the_value, the_traceback = sys.exc_info()
        print(f'Exception of type {the_type} occured in Create Image Variant. Value is {the_value}.\n'
              f'{the_traceback}')
         #print(
         #   "Unable to find {source_filename} for {full_role}; using default".format(
         #       full_role=full_role,  # SHOULD THIS BE PASSED INTO create_image_variant? Is it still relevant?
         #       source_filename=source,
         #   )#)


def find_largest_png(source: PosixPath) -> Image:
    """
    Search a directory of PNGs and returns the widest

    :param source: Directory to search
    :return: Widest PNG image
    """
    largest_image = None
    img_files = source.glob("*.png")
    img_files = list(img_files)
    if img_files:

        try:
            largest_image = Image.open(img_files.pop())

            for img in img_files:

                maybe_larger_img = Image.open(img)

                # Compare widths
                if maybe_larger_img.size[0] > largest_image.size[0]:
                    largest_image = maybe_larger_img

        except OSError:
            print("Image file cannot be read")
        except UnidentifiedImageError:
            print("Image cannot be opened and identified.")
        except FileNotFoundError:
            print("Image file cannot be found")
        except ValueError:
            print("Mode is not “r”, or a StringIO instance is used for fp")
        except TypeError:
            print("If formats is not None, a list or a tuple")


    else:
        print(f"No images in {source}")

    return largest_image

def create_icns(target: PosixPath, image: Image) -> None: #? : # I think it would be much more clear if we could return the .icns file here somehow, then we can only have the final file writing occur in the parent method.
    """
    Create a .icns file at target

    :param target: Directory
    :param image: Large PNG file

    """

    with TemporaryDirectory() as tmpdirname:
        tmpdir = PosixPath(tmpdirname)
        icon_dir = tmpdir / 'myicon.iconset'
        icon_dir.mkdir()

        filenames = ['icon_512x512@2x.png',
                     'icon_512x512.png',
                     'icon_256x256@2x.png',
                     'icon_256x256.png',
                     'icon_128x128@2x.png',
                     'icon_128x128.png',
                     'icon_32x32@2x.png',
                     'icon_32x32.png',
                     'icon_16x16@2x.png',
                     'icon_16x16.png']

        sizes = [(1024, 1024),
                 (512, 512),
                 (512, 512),
                 (256, 256),
                 (256, 256),
                 (128, 128),
                 (64, 64),
                 (32, 32),
                 (32, 32),
                 (16, 16)]




        # Convert to all sizes and write
        for f_name, size in zip(filenames, sizes):
            print(f'Creating {f_name} with size {size}')

            out_path = icon_dir / f_name
            image.resize(size).save(out_path)

        # Create the .icns file
        completed_proc = subprocess.run(['iconutil', '-c', 'icns', 'myicon.iconset'], cwd=tmpdir)


        # # Make sure the target directory exists
        target.parent.mkdir(parents=True, exist_ok=True)
        # Copy the source image to the target location
        shutil.copy(tmpdir / 'myicon.icns', target)

