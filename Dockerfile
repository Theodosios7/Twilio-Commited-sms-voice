# Use an official Python runtime as a parent image
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Install necessary tools and libraries
RUN apt-get update && apt-get install -y \
    glpk-utils \
    gfortran \
    build-essential \
    wget \
    git \
    pkg-config \
    libblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Miniconda to manage IPOPT and other complex dependencies
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /miniconda.sh \
    && bash /miniconda.sh -b -p /miniconda \
    && rm /miniconda.sh
ENV PATH="/miniconda/bin:${PATH}"

# Copy the current directory contents into the container at /app
COPY . /app

# Install Python packages from requirements.txt
RUN pip install --trusted-host pypi.python.org -r requirements.txt

# Install IPOPT via Conda
RUN conda install -c conda-forge ipopt

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable
ENV NAME World

# Run your application
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "twilio_commited_pricing_sms:app"]
