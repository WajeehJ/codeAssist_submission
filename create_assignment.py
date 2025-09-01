import docker
import os 
import zipfile
import tempfile

client = docker.from_env()

def build_image(zip_path, image_tag, target_dir):
    with tempfile.TemporaryDirectory() as build_ctx:
        # 1. Extract zip into temp dir/autograder
        extract_dir = os.path.join(build_ctx, "autograder")
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        # 2. Write a Dockerfile into build context
        dockerfile_path = os.path.join(build_ctx, "Dockerfile")
        with open(dockerfile_path, "w") as df:
            df.write(f"""
                        FROM python:3.11-slim

                        RUN mkdir -p {target_dir}

                        # Copy extracted files into container
                        COPY autograder/ {target_dir}/

                        WORKDIR {target_dir}
                    """)

        # 3. Build the image
        image, logs = client.images.build(
            path=build_ctx,
            tag=image_tag,
            rm=True
        )

    return image 


def create_container(image):
    
    container = client.containers.create(image)






    
