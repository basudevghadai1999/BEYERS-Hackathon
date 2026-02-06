import os

def create_aic_structure():
    # Root directory name
    root = "autonomous-incident-commander"
    
    # List of all files to create based on plan.md
    files = [
        "Dockerfile",
        "requirements.txt",
        ".env",
        "arch.md",
        "tools.md",
        "CLOUDWATCH_TRIGGER_GUIDE.md",
        "app/__init__.py",
        "app/handler.py",
        "app/bootstrap.py",
        "app/agents/__init__.py",
        "app/agents/commander.py",
        "app/agents/logs_agent.py",
        "app/agents/metrics_agent.py",
        "app/agents/deploy_agent.py",
        "app/tools/__init__.py",
        "app/tools/parse_alarm.py",
        "app/tools/cloudwatch_logs.py",
        "app/tools/cloudwatch_metrics.py",
        "app/tools/s3_deployments.py",
        "app/tools/stack_parser.py",
        "app/tools/anomaly_detector.py",
        "app/tools/deploy_correlator.py",
        "app/tools/state_store.py",
        "app/tools/report_generator.py",
        "app/tools/notifier.py",
        "app/tools/envelope.py",
        "app/prompts/commander_plan.txt",
        "app/prompts/commander_decide.txt",
        "app/prompts/logs_agent.txt",
        "app/prompts/metrics_agent.txt",
        "app/prompts/deploy_agent.txt",
        "seeder/handler.py",
        "seeder/seed_logs.py",
        "seeder/seed_metrics.py",
        "seeder/requirements.txt",
        "infra/app.py",
        "infra/cdk.json",
        "infra/stacks/ecr_stack.py",
        "infra/stacks/data_stack.py",
        "infra/stacks/compute_stack.py",
        "infra/stacks/events_stack.py",
        "infra/stacks/notification_stack.py",
        "tests/test_parse_alarm.py",
        "tests/test_tools.py",
        "tests/test_local_invoke.py"
    ]

    print(f"🚀 Initializing AIC Project Structure in: {os.getcwd()}")

    for file_path in files:
        # Construct path relative to script execution location
        full_path = os.path.join(root, file_path)
        
        # Extract directory and create it if it doesn't exist
        directory = os.path.dirname(full_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            
        # Create the empty file
        with open(full_path, "w", encoding="utf-8") as f:
            if file_path.endswith(".py"):
                f.write("#!/usr/bin/env python3\n")
            else:
                f.write("")
                
    print(f"✅ Successfully created {len(files)} files across the AIC directory tree.")

if __name__ == "__main__":
    create_aic_structure()