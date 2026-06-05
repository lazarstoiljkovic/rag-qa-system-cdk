#!/bin/bash

# RAG Q&A System - Helper Script
# This script provides common commands for managing the project

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project info
PROJECT_NAME="rag-qa-system-cdk"
PROJECT_DIR="/Users/lazarstoiljkovic/Desktop/other/diplomski/rag-qa-system-cdk"

echo -e "${GREEN}🤖 RAG Q&A System - Helper Script${NC}\n"

# Function to display menu
show_menu() {
    echo "Available commands:"
    echo "1) setup      - Install dependencies and build"
    echo "2) build      - Build TypeScript"
    echo "3) test       - Run tests"
    echo "4) synth      - Synthesize CloudFormation"
    echo "5) diff-kb    - Show changes for Knowledge Base stack"
    echo "6) diff-os    - Show changes for OpenSearch stack"
    echo "7) deploy-kb  - Deploy Knowledge Base stack"
    echo "8) deploy-os  - Deploy OpenSearch stack"
    echo "9) deploy-all - Deploy both stacks"
    echo "10) outputs    - Show stack outputs"
    echo "11) logs-kb    - Tail Knowledge Base Lambda logs"
    echo "12) logs-os    - Tail OpenSearch Lambda logs"
    echo "13) destroy    - Destroy all stacks"
    echo "14) clean      - Clean build artifacts"
    echo "15) docs       - Open documentation"
    echo "16) test-api   - Test API endpoints"
    echo "q) quit"
    echo ""
}

# Function to check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"
    
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js not found${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Node.js found: $(node --version)${NC}"
    
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}❌ npm not found${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ npm found: $(npm --version)${NC}"
    
    if ! command -v aws &> /dev/null; then
        echo -e "${RED}❌ AWS CLI not found${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ AWS CLI found: $(aws --version)${NC}"
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker not found${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Docker found: $(docker --version)${NC}"
    
    if ! command -v cdk &> /dev/null; then
        echo -e "${RED}❌ CDK not found${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ CDK found: $(cdk --version)${NC}"
    
    echo ""
}

# Setup
setup() {
    echo -e "${YELLOW}Setting up project...${NC}"
    npm install
    npm run build
    echo -e "${GREEN}✓ Setup complete${NC}"
}

# Build
build() {
    echo -e "${YELLOW}Building TypeScript...${NC}"
    npm run build
    echo -e "${GREEN}✓ Build complete${NC}"
}

# Test
run_tests() {
    echo -e "${YELLOW}Running tests...${NC}"
    npm test
}

# Synth
synth() {
    echo -e "${YELLOW}Synthesizing CloudFormation...${NC}"
    cdk synth
}

# Diff
diff_kb() {
    echo -e "${YELLOW}Showing changes for Knowledge Base stack...${NC}"
    cdk diff KnowledgeBaseStack
}

diff_os() {
    echo -e "${YELLOW}Showing changes for OpenSearch stack...${NC}"
    cdk diff CustomOpenSearchStack
}

# Deploy
deploy_kb() {
    echo -e "${YELLOW}Deploying Knowledge Base stack...${NC}"
    npm run deploy:knowledge-base
    echo -e "${GREEN}✓ Knowledge Base stack deployed${NC}"
}

deploy_os() {
    echo -e "${YELLOW}Deploying OpenSearch stack...${NC}"
    echo -e "${YELLOW}⏱ This will take 20-30 minutes...${NC}"
    npm run deploy:opensearch
    echo -e "${GREEN}✓ OpenSearch stack deployed${NC}"
}

deploy_all() {
    echo -e "${YELLOW}Deploying all stacks...${NC}"
    npm run deploy:all
    echo -e "${GREEN}✓ All stacks deployed${NC}"
}

# Outputs
show_outputs() {
    echo -e "${YELLOW}Knowledge Base Stack Outputs:${NC}"
    aws cloudformation describe-stacks \
        --stack-name KnowledgeBaseStack \
        --query 'Stacks[0].Outputs' \
        --output table 2>/dev/null || echo "Stack not found"
    
    echo -e "\n${YELLOW}OpenSearch Stack Outputs:${NC}"
    aws cloudformation describe-stacks \
        --stack-name CustomOpenSearchStack \
        --query 'Stacks[0].Outputs' \
        --output table 2>/dev/null || echo "Stack not found"
}

# Logs
logs_kb() {
    echo -e "${YELLOW}Tailing Knowledge Base query logs...${NC}"
    aws logs tail /aws/lambda/rag-kb-qa-query --follow
}

logs_os() {
    echo -e "${YELLOW}Tailing OpenSearch query logs...${NC}"
    aws logs tail /aws/lambda/rag-os-qa-query --follow
}

# Destroy
destroy() {
    echo -e "${RED}⚠️  WARNING: This will destroy all resources!${NC}"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" == "yes" ]; then
        echo -e "${YELLOW}Destroying stacks...${NC}"
        npm run destroy:all
        echo -e "${GREEN}✓ Stacks destroyed${NC}"
    else
        echo "Cancelled"
    fi
}

# Clean
clean() {
    echo -e "${YELLOW}Cleaning build artifacts...${NC}"
    rm -rf cdk.out
    rm -rf node_modules
    find . -name "*.js" -not -path "./node_modules/*" -delete
    find . -name "*.d.ts" -not -path "./node_modules/*" -delete
    echo -e "${GREEN}✓ Clean complete${NC}"
}

# Docs
open_docs() {
    echo -e "${YELLOW}Opening documentation...${NC}"
    if command -v open &> /dev/null; then
        open README.md
    elif command -v xdg-open &> /dev/null; then
        xdg-open README.md
    else
        echo "README.md"
    fi
}

# Test API
test_api() {
    echo -e "${YELLOW}Testing API endpoints...${NC}"
    
    # Get API endpoints
    KB_API=$(aws cloudformation describe-stacks \
        --stack-name KnowledgeBaseStack \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
        --output text 2>/dev/null)
    
    OS_API=$(aws cloudformation describe-stacks \
        --stack-name CustomOpenSearchStack \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
        --output text 2>/dev/null)
    
    if [ -n "$KB_API" ]; then
        echo -e "${GREEN}Knowledge Base API: $KB_API${NC}"
        
        # Test upload
        if [ -f "test-documents/sr/aws-uvod.txt" ]; then
            echo -e "\n${YELLOW}Testing document upload...${NC}"
            BASE64=$(base64 -i test-documents/sr/aws-uvod.txt)
            curl -s -X POST "${KB_API}documents" \
                -H "Content-Type: application/json" \
                -d "{\"file\":\"$BASE64\",\"filename\":\"aws-uvod.txt\",\"language\":\"sr\"}" | jq '.'
        fi
        
        # Test query
        echo -e "\n${YELLOW}Testing Q&A query...${NC}"
        curl -s -X POST "${KB_API}qa" \
            -H "Content-Type: application/json" \
            -d '{"question":"Šta je AWS?","language":"sr"}' | jq '.'
    else
        echo -e "${RED}Knowledge Base stack not deployed${NC}"
    fi
    
    if [ -n "$OS_API" ]; then
        echo -e "\n${GREEN}OpenSearch API: $OS_API${NC}"
    else
        echo -e "${RED}OpenSearch stack not deployed${NC}"
    fi
}

# Main loop
cd "$PROJECT_DIR" || exit 1

# Check if running with argument
if [ $# -eq 1 ]; then
    case "$1" in
        setup) check_prerequisites && setup ;;
        build) build ;;
        test) run_tests ;;
        synth) synth ;;
        diff-kb) diff_kb ;;
        diff-os) diff_os ;;
        deploy-kb) deploy_kb ;;
        deploy-os) deploy_os ;;
        deploy-all) deploy_all ;;
        outputs) show_outputs ;;
        logs-kb) logs_kb ;;
        logs-os) logs_os ;;
        destroy) destroy ;;
        clean) clean ;;
        docs) open_docs ;;
        test-api) test_api ;;
        *) echo "Unknown command: $1" && show_menu ;;
    esac
else
    # Interactive mode
    while true; do
        show_menu
        read -p "Select option: " choice
        
        case "$choice" in
            1) check_prerequisites && setup ;;
            2) build ;;
            3) run_tests ;;
            4) synth ;;
            5) diff_kb ;;
            6) diff_os ;;
            7) deploy_kb ;;
            8) deploy_os ;;
            9) deploy_all ;;
            10) show_outputs ;;
            11) logs_kb ;;
            12) logs_os ;;
            13) destroy ;;
            14) clean ;;
            15) open_docs ;;
            16) test_api ;;
            q|Q) echo -e "${GREEN}Goodbye!${NC}" && exit 0 ;;
            *) echo -e "${RED}Invalid option${NC}" ;;
        esac
        
        echo ""
        read -p "Press enter to continue..."
    done
fi
