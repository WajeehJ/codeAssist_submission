import docker
import os 
import zipfile
import tempfile
import uuid
import json
import shutil

client = docker.from_env()


"""
notes: 
Make sure that Docker is running
Run python3 create_assignment.py to see the results
"""


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
            df.write(f"""FROM python:3.11-slim

# Install required packages
RUN pip install gradescope-utils

# Create the main autograder directory
RUN mkdir -p /autograder

# Copy extracted files into container
COPY autograder/ /autograder/

# Create required directories
RUN mkdir -p /autograder/submission
RUN mkdir -p /autograder/source
RUN mkdir -p /autograder/results

# Copy test files to source directory
RUN cp /autograder/run_tests.py /autograder/source/
RUN cp -r /autograder/tests /autograder/source/

# Make run_autograder executable
RUN chmod +x /autograder/run_autograder

WORKDIR /autograder
""")

        # 3. Build the image
        image, logs = client.images.build(
            path=build_ctx,
            tag=image_tag,
            rm=True
        )

    return image 


def create_container(image):
    container = client.containers.create(
        image=image,
        tty=True,
        command="tail -f /dev/null",  # Keep container alive
        detach=True
    )
    container.start()
    return container
    
def create_test_assignment():
    '''Using A1 for test'''
    assignment_id = str(uuid.uuid4())
    assignment_name = "A1"
        
    test_zip = os.path.join(os.path.dirname(__file__), "assignment-examples", "A1", "A1.zip")
    target_dir = "/autograder"  
    image_tag = f"autograder:{assignment_id}"

    #build image
    image = build_image(test_zip, image_tag, target_dir)

    #create container
    container = create_container(image)

    #create submission directory on host
    submission_dir = os.path.join(os.path.dirname(__file__), "submissions", assignment_id)
    os.makedirs(submission_dir, exist_ok=True)

    #copy submission file into submission directory
    submission_file_src = os.path.join(os.path.dirname(__file__), "assignment-examples", "A1", "calculator.py")
    submission_file_dst = os.path.join(submission_dir, "calculator.py")
    shutil.copy2(submission_file_src, submission_file_dst)


    assignment_data = {
        "id": assignment_id,
        "name": assignment_name,
        "autograder_image": image_tag,
        "container_id": container.id if container else None,
        "submission_dir": submission_dir
    }

    print(f"Assignment created: {assignment_id}")
    return assignment_data

def run_autograder(container, submission_file_path):
    """Run the autograder inside the container"""
    import tarfile
    import io
    
    # Copy submission file to container
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        tar.add(submission_file_path, arcname=os.path.basename(submission_file_path))
    tar_stream.seek(0)
    
    # Put the submission in the container
    container.put_archive("/autograder/submission/", tar_stream)
    
    # Run the autograder
    print("Running autograder...")
    exec_result = container.exec_run("/bin/bash /autograder/run_autograder")
    
    if exec_result.exit_code != 0:
        print(f"Autograder execution failed: {exec_result.output.decode()}")
        return None
    
    # Get results
    results_result = container.exec_run("cat /autograder/results/results.json")
    if results_result.exit_code == 0:
        results_json = results_result.output.decode()
        return json.loads(results_json)
    else:
        print("Failed to retrieve results")
        return None

def get_results(assignment_data):
    """Get the results from the autograder run"""
    container_id = assignment_data["container_id"]
    submission_dir = assignment_data["submission_dir"]
    target_dir = "/autograder"
    
    # Get the container
    container = client.containers.get(container_id)
    
    # Find the submission file
    submission_file = os.path.join(submission_dir, "calculator.py")
    if not os.path.exists(submission_file):
        print(f"Submission file not found: {submission_file}")
        return None
    
    print(f"Running autograder on: {submission_file}")
    results = run_autograder(container, submission_file, target_dir)
    
    if results:
        print(f"✓ Autograder completed successfully!")
        print(f"✓ Score: {results.get('score', 'N/A')}")
        
        # Save results to file
        results_file = os.path.join(submission_dir, "results.json")
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"✓ Results saved to: {results_file}")
        
        return results
    else:
        print("Autograder failed")
        return None

def main():
    print("=== Testing CodeAssist Submission System ===\n")
    
    try:
        #create test assignment
        print("1. Creating test assignment...")
        assignment_data = create_test_assignment()
        print(f"   Assignment ID: {assignment_data['id']}")
        print(f"   Container ID: {assignment_data['container_id']}")
        print(f"   Submission dir: {assignment_data['submission_dir']}\n")
        
        #run autograder and get results
        print("2. Running autograder...")
        results = get_results(assignment_data)
        
        if results:
            print("\n" + "="*50)
            print("🎉 SUCCESS! Container is working perfectly!")
            print("="*50)
            print(f"📊 Final Score: {results.get('score', 'N/A')}")
            print(f"⏱️  Execution Time: {results.get('execution_time', 'N/A')}s")
            print(f"📁 Results saved to: {assignment_data['submission_dir']}/results.json")
            print("\n✅ Your container reuse system is ready!")
        else:
            print("\n❌ FAILED")
            print("Autograder execution failed. Check the error messages above.")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()