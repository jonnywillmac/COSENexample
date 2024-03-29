# Start with this container as the base
FROM ibmfunctions/action-python-v3.7

# add package build dependencies
RUN apt update
RUN apt install -y \
        ffmpeg

# add python packages
RUN pip3 install --upgrade pip
RUN pip3 install \
    ibm_cos_sdk