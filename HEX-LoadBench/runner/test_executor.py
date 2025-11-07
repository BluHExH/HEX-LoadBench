"""
Test execution service that coordinates load tests using k6 or Python runner.
Handles different load profiles and manages test lifecycle.
"""

import os
import json
import subprocess
import asyncio
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging
from pathlib import Path

from runner.python_runner.load_runner import LoadRunner, LoadTestConfig

logger = logging.getLogger(__name__)

class TestExecutor:
    """Coordinates execution of load tests using different runners."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.execution_id = str(uuid.uuid4())
        self.is_running = False
        self.process = None
        self.metrics = {}
        
    async def execute_test(self, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a load test based on configuration."""
        
        logger.info(f"Starting test execution {self.execution_id}")
        self.is_running = True
        
        try:
            # Choose runner based on test requirements
            if test_config.get("runner_type") == "python" or test_config.get("concurrent_users", 0) < 1000:
                return await self._run_python_test(test_config)
            else:
                return await self._run_k6_test(test_config)
                
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "execution_id": self.execution_id
            }
        finally:
            self.is_running = False
    
    async def _run_k6_test(self, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute test using k6."""
        
        # Select appropriate k6 script based on load profile
        profile_type = test_config.get("load_profile_type", "steady_state")
        script_path = self._get_k6_script_path(profile_type)
        
        if not script_path or not os.path.exists(script_path):
            raise ValueError(f"k6 script not found for profile: {profile_type}")
        
        # Prepare environment variables for k6
        env_vars = self._prepare_k6_env(test_config)
        
        # Build k6 command
        cmd = [
            "k6", "run", 
            "--out", "json=results.json",
            "--summary-export=summary.json",
            script_path
        ]
        
        # Add duration override if specified
        if test_config.get("duration"):
            cmd.extend(["--duration", f"{test_config['duration']}s"])
        
        # Execute k6 test
        logger.info(f"Executing k6 command: {' '.join(cmd)}")
        
        try:
            # Run k6 process
            self.process = subprocess.Popen(
                cmd,
                env={**os.environ, **env_vars},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for completion with timeout
            try:
                stdout, stderr = self.process.communicate(timeout=test_config.get("timeout", 3600))
                return_code = self.process.returncode
                
                if return_code == 0:
                    # Parse k6 results
                    results = self._parse_k6_results()
                    return {
                        "success": True,
                        "execution_id": self.execution_id,
                        "runner": "k6",
                        "results": results,
                        "stdout": stdout,
                        "duration": test_config.get("duration")
                    }
                else:
                    return {
                        "success": False,
                        "execution_id": self.execution_id,
                        "error": f"k6 failed with return code {return_code}",
                        "stderr": stderr
                    }
                    
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
                return {
                    "success": False,
                    "execution_id": self.execution_id,
                    "error": "Test execution timed out"
                }
                
        except Exception as e:
            logger.error(f"k6 execution error: {e}")
            return {
                "success": False,
                "execution_id": self.execution_id,
                "error": f"k6 execution failed: {str(e)}"
            }
    
    async def _run_python_test(self, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute test using Python runner."""
        
        # Create LoadTestConfig
        python_config = LoadTestConfig(
            target_url=test_config["target_url"],
            method=test_config.get("method", "GET"),
            headers=test_config.get("headers", {}),
            body=test_config.get("body_template", ""),
            auth_token=test_config.get("auth_token", ""),
            concurrent_users=test_config.get("concurrent_users", 10),
            duration=test_config.get("duration", 60),
            max_rps=test_config.get("rps_limit", 100),
            timeout=test_config.get("timeout", 30)
        )
        
        # Run Python load test
        async with LoadRunner(python_config) as runner:
            metrics = await runner.run_test()
            report = runner.generate_report()
            
            return {
                "success": True,
                "execution_id": self.execution_id,
                "runner": "python",
                "results": report,
                "metrics": {
                    "total_requests": metrics.total_requests,
                    "successful_requests": metrics.successful_requests,
                    "failed_requests": metrics.failed_requests,
                    "response_times": metrics.response_times
                }
            }
    
    def _get_k6_script_path(self, profile_type: str) -> Optional[str]:
        """Get the path to the appropriate k6 script."""
        script_mapping = {
            "ramp_up": "runner/k6-scripts/ramp-up-test.js",
            "steady_state": "runner/k6-scripts/basic-load-test.js",
            "spike": "runner/k6-scripts/spike-test.js",
            "soak": "runner/k6-scripts/soak-test.js"
        }
        
        return script_mapping.get(profile_type)
    
    def _prepare_k6_env(self, test_config: Dict[str, Any]) -> Dict[str, str]:
        """Prepare environment variables for k6 script."""
        env_vars = {
            "TARGET_URL": test_config["target_url"],
            "TARGET_METHOD": test_config.get("method", "GET"),
            "TARGET_HEADERS": json.dumps(test_config.get("headers", {})),
            "TARGET_BODY": test_config.get("body_template", ""),
            "AUTH_TOKEN": test_config.get("auth_token", ""),
            "TEST_DURATION": f"{test_config.get('duration', 600)}s",
            "MAX_RPS": str(test_config.get("rps_limit", 1000))
        }
        
        # Add load profile specific variables
        profile_config = test_config.get("load_profile_config", {})
        
        if test_config.get("load_profile_type") == "ramp_up":
            env_vars.update({
                "INITIAL_USERS": str(profile_config.get("initial_users", 1)),
                "TARGET_USERS": str(profile_config.get("target_users", 100)),
                "RAMP_DURATION": str(profile_config.get("ramp_duration", 300)),
                "HOLD_DURATION": str(profile_config.get("hold_duration", 600))
            })
        elif test_config.get("load_profile_type") == "spike":
            env_vars.update({
                "BASELINE_USERS": str(profile_config.get("baseline_users", 10)),
                "SPIKE_USERS": str(profile_config.get("spike_users", 1000)),
                "SPIKE_DURATION": str(profile_config.get("spike_duration", 60)),
                "BASELINE_DURATION": str(profile_config.get("baseline_duration", 300))
            })
        elif test_config.get("load_profile_type") == "soak":
            env_vars.update({
                "CONCURRENT_USERS": str(profile_config.get("concurrent_users", 50)),
                "SOAK_DURATION": str(test_config.get("duration", 86400))
            })
        
        return env_vars
    
    def _parse_k6_results(self) -> Dict[str, Any]:
        """Parse k6 results files."""
        results = {}
        
        # Parse summary.json
        try:
            if os.path.exists("summary.json"):
                with open("summary.json", "r") as f:
                    summary = json.load(f)
                    results["summary"] = summary
        except Exception as e:
            logger.warning(f"Failed to parse k6 summary: {e}")
        
        # Parse results.json (detailed metrics)
        try:
            if os.path.exists("results.json"):
                metrics = []
                with open("results.json", "r") as f:
                    for line in f:
                        if line.strip():
                            metrics.append(json.loads(line))
                    results["detailed_metrics"] = metrics
        except Exception as e:
            logger.warning(f"Failed to parse k6 detailed results: {e}")
        
        return results
    
    def abort_test(self) -> Dict[str, Any]:
        """Abort the currently running test."""
        if not self.is_running:
            return {"success": False, "error": "No test is currently running"}
        
        logger.info(f"Aborting test execution {self.execution_id}")
        
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
                return {"success": True, "message": "Test aborted successfully"}
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
                return {"success": True, "message": "Test forcefully terminated"}
            except Exception as e:
                return {"success": False, "error": f"Failed to abort test: {str(e)}"}
        
        return {"success": False, "error": "No process to abort"}

# Test execution manager for handling multiple tests
class TestExecutionManager:
    """Manages multiple test executions."""
    
    def __init__(self):
        self.active_tests = {}
        self.max_concurrent_tests = 5
    
    async def start_test(self, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Start a new test execution."""
        
        # Check concurrent test limit
        if len(self.active_tests) >= self.max_concurrent_tests:
            return {
                "success": False,
                "error": f"Maximum concurrent tests ({self.max_concurrent_tests}) reached"
            }
        
        # Create executor
        executor = TestExecutor(test_config)
        self.active_tests[executor.execution_id] = executor
        
        try:
            # Execute test in background
            results = await executor.execute_test(test_config)
            
            # Clean up
            if executor.execution_id in self.active_tests:
                del self.active_tests[executor.execution_id]
            
            return results
            
        except Exception as e:
            # Clean up on error
            if executor.execution_id in self.active_tests:
                del self.active_tests[executor.execution_id]
            
            return {
                "success": False,
                "error": f"Test execution failed: {str(e)}"
            }
    
    def abort_test(self, execution_id: str) -> Dict[str, Any]:
        """Abort a specific test execution."""
        
        if execution_id not in self.active_tests:
            return {"success": False, "error": "Test execution not found"}
        
        executor = self.active_tests[execution_id]
        result = executor.abort_test()
        
        # Clean up
        if execution_id in self.active_tests:
            del self.active_tests[execution_id]
        
        return result
    
    def get_active_tests(self) -> Dict[str, str]:
        """Get list of active test executions."""
        return {
            execution_id: "running" if executor.is_running else "completed"
            for execution_id, executor in self.active_tests.items()
        }

# Global execution manager instance
execution_manager = TestExecutionManager()