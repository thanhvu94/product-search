pipeline {
    // Run this pipeline on any agent
    agent any

    options{
        // Max number of build logs to keep and days to keep
        buildDiscarder(logRotator(numToKeepStr: '5', daysToKeepStr: '5'))
        // Display timestamp at each job in the pipeline
        timestamps()
    }

    // Input parameters of your VM
    parameters {
        string(name: 'PROD_SERVER_IP', defaultValue: '127.0.0.1', description: 'Public IP of the target VM.')
        string(name: 'PROD_SERVER_USER', defaultValue: 'ubuntu', description: 'SSH Username of the target VM.')
    }

    // Environment variables
    environment {
        // Docker
        DOCKER_HUB_USER         = "vunt94"
        IMAGE_NAME              = "product-search-app"
        DOCKER_CREDENTIAL_ID    = "docker-creds"
        
        // SSH credential on EC2 VM (GCP)
        SSH_CREDENTIAL_ID       = "prod-ssh-key"
        PROD_COMPOSE_PATH       = "/home/${env.PROD_SERVER_USER}/product-search"

        // Pinecone
        PINECONE_CREDENTIAL_ID = "pinecone-api-key"

        // Run Jenkins with same version as Docker
        DOCKER_API_VERSION      = "1.41"
    }

    stages {
        stage('Test') {
            agent {
                docker {
                    image 'python:3.11'
                    args "-e TESTING_MODE=true"
                }
            }
            steps {
                withCredentials([string(credentialsId: env.PINECONE_CREDENTIAL_ID, variable: 'PINECONE_API_KEY')]) {
                    echo 'Testing model ...'
                    sh """
                        export PINECONE_API_KEY=${env.PINECONE_API_KEY}
                        pip install --timeout=600 -r requirements.txt && pytest
                    """
                }
            }
        }

        stage('Build') {
            steps {
                script {
                    echo "Building image for deployment..."
                    // Build application image (tag build number)
                    def dockerImage = docker.build("${env.DOCKER_HUB_USER}/${env.IMAGE_NAME}:${env.BUILD_NUMBER}", ".")
                    
                    echo "Pushing image to dockerhub..."
                    // Log in to Docker Hub using our credential ID & push image with latest tag
                    docker.withRegistry("https://registry.hub.docker.com", env.DOCKER_CREDENTIAL_ID) {
                        dockerImage.push()
                        dockerImage.push("latest")
                    }
                }
            }
        }

        stage('Deploy') {
            steps {
                echo "Deploying new image to server..."
                withCredentials([string(credentialsId: env.PINECONE_CREDENTIAL_ID, variable: 'PINECONE_API_KEY')]) {
                    // Login to EC2 VM
                    sshagent([env.SSH_CREDENTIAL_ID]) {
                        script {
                            def CLUSTER_NAME = "product-search"
                            def ZONE = "us-central1-f"
                            def IMAGE_TAG = "${env.DOCKER_HUB_USER}/${env.IMAGE_NAME}:${env.BUILD_NUMBER}"

                            sh """
                                ssh -o StrictHostKeyChecking=no ${env.PROD_SERVER_USER}@${env.PROD_SERVER_IP} '''
                                    echo "Logged in to production server!"

                                    # Setup PINECONE_API_KEY for the remote shell session
                                    export PINECONE_API_KEY='${env.PINECONE_API_KEY}'
                                    
                                    # Navigate to the docker-compose project directory
                                    cd ${env.PROD_COMPOSE_PATH}
                                    
                                    # --- 1. GKE AUTHENTICATION ---
                                    echo "Connecting to GKE cluster: ${CLUSTER_NAME}"
                                    if gcloud container clusters describe ${CLUSTER_NAME} --zone ${ZONE} &> /dev/null; then
                                        echo "GKE cluster ${CLUSTER_NAME} already exists. Getting credentials..."
                                    else
                                        echo "GKE cluster ${CLUSTER_NAME} not found. Creating new cluster..."
                                        # Customize the cluster size and machine type as needed
                                        gcloud container clusters create ${CLUSTER_NAME} \
                                            --zone ${ZONE} \
                                            --num-nodes=3 \
                                            --machine-type=e2-medium \
                                            --disk-size=50                             
                                        echo "Cluster ${CLUSTER_NAME} successfully created and ready."
                                    fi
                                    gcloud container clusters get-credentials ${CLUSTER_NAME} --zone ${ZONE}

                                    # --- 2. DEPLOY APPLICATION TO K8S (3 REPLICAS) ---
                                    echo "Applying Kubernetes configuration with 3 replicas and image tag: ${IMAGE_TAG}"
                                    kubectl apply -f k8s/secret.yaml
                                    kubectl apply -f k8s/product-search.yaml

                                    echo "Waiting for Deployment to be ready..."
                                    kubectl rollout status deployment/product-search-app --timeout=5m
                                    kubectl get pods -l app=product-search

                                    # --- 3. MONITORING SETUP (HELM & PROMETHEUS) ---
                                    echo "Adding Prometheus Helm repository and updating..."
                                    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts || true
                                    helm repo update

                                    echo "Creating monitoring namespace..."
                                    kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

                                    echo "Installing kube-prometheus-stack..."
                                    helm upgrade -i prometheus-stack prometheus-community/kube-prometheus-stack \\
                                                --namespace monitoring \\
                                                --set grafana.adminPassword='admin'
                                    
                                    echo "Telling Prometheus to scrape metrics from product-search..."
                                    kubectl label service product-search-service app=product-search --overwrite
                                    kubectl apply -f k8s/service-monitor.yaml
                                    
                                    echo "Deployment and Monitoring setup complete!"
                                '''
                            """
                        }
                    }
                }
            }
        }
    }
}