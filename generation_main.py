import concurrent.futures
import json
import multiprocessing
import os
import subprocess
import shutil
import random
import cv2
import skimage
import numpy as np
from queue import Empty
import threading
import time
import argparse

from skimage.util import img_as_float, img_as_uint
from tqdm import tqdm



def run_command(command, progress_queue, verbose):
    """
    Calls the blender executable with the specified arguments and monitors the progress of the instance, should the
    instance hang or crash it will be restarted resuming the generation from the progress.


    :param command: list containing command information.
    :param progress_queue: thread queue used to communicate progress back to the main thread.
    :param verbose: print to the terminal.
    """
    complete = False

    # command to start blender instance
    process_command = command[0]
    # list of filenames to render
    filename_list = list(range(command[1], command[2]))
    # index of the blender instance
    process_index = command[3]

    while not complete:

        process_command.append(json.dumps(filename_list))

        process = subprocess.Popen(process_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

        last_message_time = [time.time()]
        timeout = 300
        def check_timeout():
            if time.time() - last_message_time[0] > timeout:
                process.kill()
                raise Exception("Process timed out due to inactivity.")

        def monitor_process():
            while process.poll() is None:  # While process is running
                time.sleep(1)
                check_timeout()

        monitor_thread = threading.Thread(target=monitor_process)
        monitor_thread.start()

        try:
            for line in process.stdout:
                last_message_time[0] = time.time()  # Update the last message time

                if "PROGRESS" in line:
                    progress_queue.put(1)
                elif "GENERATION_SUCCESSFUL" in line:
                    complete = True
                    break
                elif "FILENAME" in line:
                    filename_list.remove(int(line.removeprefix("FILENAME:")))
                elif "error" in line.lower():
                    print(line.strip())
                if verbose:
                    print(str(process_index) + ": " + line.strip())

            process.communicate()
            monitor_thread.join()  # Ensure monitor thread finishes

        except KeyboardInterrupt:
            print("KeyboardInterrupt caught. Terminating subprocess.")
            process.kill()
            monitor_thread.join()
            break

        except Exception as e:
            print(e)
            monitor_thread.join()  # Ensure monitor thread finishes
            continue  # Restart the process

def clear_directory(directory_path):
    """
    Remove a directory and its content.
    :param directory_path: Path to the directory to remove.
    """
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')

def rename_files(directory, already_processed = None):
    """
    Concatenates filenames of a directory, meaning that they will be renamed starting from 0 to the amount of files in
    the directory to enable resumed generation.

    :param directory: path to directory.
    :param already_processed: list of files that have already had post-processing applied. To keep track of them when
    renamed.
    :return: list of already processed filenames.
    """
    files = os.listdir(directory)
    files = [f for f in files if os.path.isfile(os.path.join(directory, f))]
    files.sort(key=lambda x: int(os.path.splitext(x)[0]))

    if already_processed is not None:
        already_processed = already_processed.intersection(files)

    for i, filename in enumerate(files):
        file_name, file_extension = os.path.splitext(filename)
        new_filename = str(i) + file_extension
        os.rename(os.path.join(directory, filename), os.path.join(directory, new_filename))

        if already_processed is not None and filename in already_processed:
            already_processed.discard(filename)
            already_processed.add(new_filename)
    return already_processed

def resume_generation(img_path, label_path, post_processing_file, nr_images_to_generate):
    """
    Checks that there are no corrupt images and that each label and image as a corresponding pair. If there are images
    are corrupt or files that don't have a pair they will be removed. If the generation is resumed an appropriate
    start index and amount of images to generate will be given.

    :param img_path: path to generated images
    :param label_path: path to generated labels
    :param post_processing_file: path to post-processing file.
    :param nr_images_to_generate: number of images to generate based on the given configuration.
    :return nr_images_to_generate: number of images to generate based on already generated images.
    :return start_index: start index to start from .
    """

    # initialize file to keep track of post-processing progress.
    try:
        with open(post_processing_file, 'r') as file:
            already_processed = set(line.strip() for line in file)
    except FileNotFoundError:
        already_processed = set()

    # check if there are any corrupt images that have no data.
    for file in os.listdir(img_path):
        if os.path.getsize(os.path.join(img_path, file)) == 0:
            os.remove(os.path.join(img_path, file))

    # check that each image and label has a corresponding pair
    image_files = [f for f in os.listdir(img_path) if f.endswith('.PNG')]
    txt_files = [f for f in os.listdir(label_path) if f.endswith('.txt')]

    missing_txt = [image for image in image_files if image[:-4] + '.txt' not in txt_files]
    missing_image = [txt for txt in txt_files if txt[:-4] + '.PNG' not in image_files]

    # remove labels that have no corresponding image
    for file in missing_txt:
        os.remove(os.path.join(img_path, file))

    # remove images that have no corresponding label and remove them from already processed
    for file in missing_image:
        already_processed.discard(file)
        os.remove(os.path.join(label_path, file))

    # if the image path contains more or the same amount of images
    if len(os.listdir(img_path)) >= nr_images_to_generate:
        return 0, 0

    # concatenate images and labels
    already_processed = rename_files(img_path, already_processed)
    rename_files(label_path)


    nr_images_to_generate = nr_images_to_generate - len(os.listdir(img_path))
    start_index = len(os.listdir(img_path))

    with open(post_processing_file, 'w') as file:
        for element in already_processed:
            file.write(str(element) + '\n')

    return nr_images_to_generate, start_index

def post_processing(image_path, post_processing_file, config):
    """
    Apply post-processing blur and noise. To keep track of which images have applied post-processing a file is used.

    :param image_path: path to generated images.
    :param post_processing_file: file containing image filenames that have already been post-processed.
    :param config: user configuration file.
    """
    sp_noise_probability = config["user"]["image_sp_noise_probability"]
    sp_noise_amount_min = config["user"]["image_sp_noise_amount_min"]
    sp_noise_amount_max = config["user"]["image_sp_noise_amount_max"]

    gaussian_blur_probability = config["user"]["image_gaussian_blur_probability"]
    gaussian_blur_sigma_min = config["user"]["image_gaussian_blur_sigma_min"]
    gaussian_blur_sigma_max = config["user"]["image_gaussian_blur_sigma_max"]


    try:
        with open(post_processing_file, 'r') as file:
            already_processed = set(line.strip() for line in file)
    except FileNotFoundError:
        already_processed = set()

    img_dir_files = os.listdir(image_path)
    img_dir_files.sort()

    images_to_process = already_processed.symmetric_difference(os.listdir(image_path))

    images_to_process = sorted(images_to_process)

    for image_file in tqdm(images_to_process):

        do_noise = random.uniform(0.0, 1.0) <= sp_noise_probability
        do_gaussian_blur = random.uniform(0.0, 1.0) <= gaussian_blur_probability

        try:
            synthetic_image = img_as_float(cv2.imread(os.path.join(image_path, image_file)))
        except ValueError as e:
            print("Failed to read image: ", str(image_file))
            raise e

        post_processing_applied = False

        if do_gaussian_blur:
            gaussian_blur_sigma = random.uniform(gaussian_blur_sigma_min, gaussian_blur_sigma_max)
            for channel in range(synthetic_image.shape[2]):
                synthetic_image[:, :, channel] = skimage.filters.gaussian(synthetic_image[:, :, channel],
                                                                        sigma=gaussian_blur_sigma)

            post_processing_applied = True


        if do_noise:
            sp_amount = random.uniform(sp_noise_amount_min, sp_noise_amount_max)
            synthetic_image = skimage.util.random_noise(synthetic_image, mode='s&p', amount=sp_amount)
            post_processing_applied = True


        if post_processing_applied:
            synthetic_image = np.clip(synthetic_image, 0, 1)
            synthetic_image = img_as_uint(synthetic_image)
            cv2.imwrite(os.path.join(image_path, image_file), synthetic_image)

        with open(post_processing_file, 'a') as file:
            file.write(image_file + '\n')
            already_processed.add(image_file)


def generate(nr_images_to_generate, nr_blender_instances, current_image_index):
    """
    starts generation process by constructing run commands for each blender instance and creates a thread for
    each instance.

    :param nr_images_to_generate: Number of images to generate.
    :param nr_blender_instances: Number of blender instance to use for generation.
    :param current_image_index: First image index to use.
    """
    quotient, remainder = divmod(nr_images_to_generate, nr_blender_instances)
    images_per_instance = [quotient] * nr_blender_instances

    for i in range(remainder):
        images_per_instance[i] += 1

    commands = []
    for i in range(nr_blender_instances):
        commands.append([[blender_path,
                          "--background",
                          '--python', blender_script_path,
                          '--',  # Separator between Blender args and script args
                          generation_config_json  # Pass the config_path as a named argument
                          ],
                         current_image_index,
                         current_image_index + images_per_instance[i],
                         i
                         ])
        # print("Executing command:", commands)
        current_image_index += images_per_instance[i]

    progress_queue = multiprocessing.Queue()

    print("Checking for opencv in Blender env...")
    subprocess.run([blender_path,
                    "--background",
                    '--python', os.path.join("Blender", "opencv_check.py"),
                    ])

    print("Starting generation...")
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(run_command, cmd, progress_queue, verbose) for cmd in commands]
        if not verbose:
            with tqdm(total=nr_images_to_generate) as pbar:
                while True:
                    try:
                        progress_queue.get_nowait()
                        pbar.update(1)  # Update the progress bar
                    except Empty:
                        pass
                    if all(future.done() for future in futures):
                        break

    progress_queue.close()
    progress_queue.join_thread()

if __name__ == '__main__':
    blender_path = os.getenv('BLENDER_PATH')
    print (blender_path)

    blender_script_path = os.path.join("Blender", "blender_run.py")

    # Create the parser
    parser = argparse.ArgumentParser(description='Process configuration file.')
     # Add an argument for the configuration file path
    parser.add_argument('--config', type=str, default="config-sample.json", help='Path to the configuration file')
    # Parse the arguments
    args = parser.parse_args()
    # Use the provided configuration file path
    config_path = args.config
    print ('blender_main_config_file', config_path)


    with open(config_path, 'r') as f_config_json:
        config_json = json.load(f_config_json)

    # setup generation paths
    render_output_path = config_json["system"]["render_output_path"]
    img_work_path = f'{render_output_path}/{config_json["system"]["img_work_path"]}'
    label_work_path = f'{render_output_path}/{config_json["system"]["label_work_path"]}'
    blender_save_path = f'{render_output_path}/{config_json["system"]["blender_work_path"]}'
    log_work_path = f'{render_output_path}/{config_json["system"]["log_work_path"]}'
    segmentation_path = f'{render_output_path}/{config_json["system"]["segmentation_work_path"]}'
    bbox_img_path = f'{render_output_path}/{config_json["system"]["bbox_img_work_path"]}'
    post_processing_file = os.path.join(render_output_path, "applied_post_processing.txt")

    config_json["img_work_path"] = img_work_path
    config_json["label_work_path"] = label_work_path
    config_json["blender_work_path"] = blender_save_path
    config_json["log_work_path"] = log_work_path
    config_json["segmentation_path"] = segmentation_path
    config_json["bbox_img_work_path"] = bbox_img_path
    config_json["gpu_ordinal_for_generation"] = -1
    config_json["continuous"] = False

    nr_images_to_generate = config_json["user"]["generate_nr_samples"]
    nr_blender_instances = config_json["user"]["nr_blender_instances"]
    clear_paths = config_json["user"]["clear_paths"]  # Reading the new clear_paths setting
    verbose = config_json["user"]["verbose"]

    generation_config_json = json.dumps(config_json)

    # create generation paths and  clear them if in settings.
    for work_path in [img_work_path, label_work_path, log_work_path, blender_save_path, segmentation_path, bbox_img_path]:
        if not os.path.exists(work_path):
            os.makedirs(work_path)
        elif clear_paths:
            clear_directory(work_path)

    if clear_paths and os.path.exists(post_processing_file):
        os.remove(post_processing_file)

    nr_images_to_generate, current_image_index = resume_generation(img_work_path, label_work_path, post_processing_file, nr_images_to_generate)

    print("Nr images to generate: ", nr_images_to_generate)
    print("Starting image index: ", current_image_index)

    # start generation
    generate(nr_images_to_generate, nr_blender_instances, current_image_index)

    # apply post-processing
    if 0.0 < config_json["user"]["image_sp_noise_probability"] or 0.0 < config_json["user"]["image_gaussian_blur_probability"]:
        print("Post processing....")
        post_processing(img_work_path, post_processing_file, config_json)