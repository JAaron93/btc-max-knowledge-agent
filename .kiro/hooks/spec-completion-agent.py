#!/usr/bin/env python3
"""
Spec Completion Monitor Agent Hook

This agent hook monitors spec task files and automatically creates completion
status files when all tasks are marked as completed.

Trigger: When tasks.md files in .kiro/specs/* are modified
Action: Check completion status and create .completed file if all tasks done
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def parse_tasks_file(tasks_file_path: str) -> Tuple[int, int, List[str]]:
    """
    Parse tasks.md file to count total and completed tasks.
    
    Returns:
        Tuple of (total_tasks, completed_tasks, task_titles)
    """
    if not os.path.exists(tasks_file_path):
        return 0, 0, []
    
    try:
        with open(tasks_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (IOError, UnicodeDecodeError) as e:
        print(f"⚠️  Error reading tasks file {tasks_file_path}: {e}")
        return 0, 0, []
    
    # Find all task lines (both completed and incomplete)
    # More robust pattern that handles:
    # - Optional leading whitespace
    # - Different bullet points (-, *, +)
    # - Uppercase/lowercase X in checkboxes
    # - Extra spaces around checkbox brackets
    task_pattern = r'^\s*[-*+]\s*\[\s*([xX ])\s*\]\s*(.+)$'
    tasks = re.findall(task_pattern, content, re.MULTILINE)
    
    total_tasks = len(tasks)
    completed_tasks = sum(1 for status, _ in tasks if status.lower() == 'x')
    task_titles = [title.strip() for _, title in tasks]
    
    return total_tasks, completed_tasks, task_titles


def get_spec_info(spec_dir: str) -> Dict[str, str]:
    """Extract spec information from requirements.md and design.md."""
    info = {}
    
    # Try to get spec name from directory
    spec_name = os.path.basename(spec_dir).replace('-', ' ').title()
    info['name'] = spec_name
    
    # Try to extract description from requirements.md
    requirements_file = os.path.join(spec_dir, 'requirements.md')
    if os.path.exists(requirements_file):
        with open(requirements_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # Look for introduction or description section with robust pattern
            # This pattern handles:
            # - Variable whitespace after header
            # - Optional newlines between header and content
            # - Matches until next section header (any level) or end of content
            # - Works with different markdown structures
            intro_match = re.search(
                r'##\s+(?:Introduction|Description|Overview)\s*\n\s*(.*?)(?=\n\s*#+\s+|\Z)', 
                content, 
                re.DOTALL | re.IGNORECASE
            )
            if intro_match:
                # Clean up the extracted content by removing extra whitespace
                description = re.sub(r'\s+', ' ', intro_match.group(1).strip())
                if description:
                    info['description'] = description[:200] + ("..." if len(description) > 200 else "")
    
    return info


def create_completion_file(spec_dir: str, total_tasks: int, completed_tasks: int, 
                          task_titles: List[str], spec_info: Dict[str, str]) -> None:
    """Create the .completed status file."""
    completion_file = os.path.join(spec_dir, '.completed')
    
    # Create template variables dictionary
    template_vars = {
        'completion_date': datetime.now().strftime('%Y-%m-%d'),
        'completion_timestamp': datetime.now().isoformat(),
        'spec_name': spec_info.get('name', 'Unknown Spec'),
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'agent_version': '1.0'
    }
    
    # Build content as structured list of lines
    content_lines = [
        "# Spec Completion Status",
        "SPEC_COMPLETED=true",
        f"COMPLETION_DATE={template_vars['completion_date']}",
        f"SPEC_NAME={template_vars['spec_name']}",
        f"TOTAL_TASKS={template_vars['total_tasks']}",
        f"COMPLETED_TASKS={template_vars['completed_tasks']}",
        "STATUS=All tasks completed successfully",
        "IMPLEMENTATION_READY=true",
        "",
        "# Task Summary"
    ]
    
    # Add task entries
    # Add task entries
    for i, task_title in enumerate(task_titles, 1):
        # Sanitize task title to prevent issues in shell-like format
        sanitized_title = task_title.replace('\n', ' ').replace('\r', '').strip()
        content_lines.append(f"TASK_{i}={sanitized_title}")
    
    # Add description if available
    if 'description' in spec_info:
        content_lines.extend([
            "",
            "# Description",
            spec_info['description']
        ])
    
    # Add completion details
    content_lines.extend([
        "",
        "# Completion Details",
        f"COMPLETION_TIMESTAMP={template_vars['completion_timestamp']}",
        f"AGENT_HOOK_VERSION={template_vars['agent_version']}",
        "AUTO_GENERATED=true",
        "",
        "# Next Steps",
        "# - Review implementation completeness",
        "# - Update project documentation",
        "# - Consider archiving spec if no future changes planned",
        "# - Celebrate the successful completion! 🎉"
    ])
    
    # Join lines and write to file
    content = '\n'.join(content_lines) + '\n'
    with open(completion_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Created completion status file: {completion_file}")


def create_completion_summary(spec_dir: str, spec_info: Dict[str, str], 
                            task_titles: List[str]) -> None:
    """Create a comprehensive completion summary if it doesn't exist."""
    summary_file = os.path.join(spec_dir, 'COMPLETION_SUMMARY.md')
    
    if os.path.exists(summary_file):
        print(f"📄 Completion summary already exists: {summary_file}")
        return
    
    completion_date = datetime.now().strftime('%Y-%m-%d')
    spec_name = spec_info.get('name', 'Unknown Spec')
    
    content = f"""# {spec_name} - Completion Summary

## Project Status: ✅ COMPLETED
**Completion Date:** {completion_date}
**Total Tasks:** {len(task_titles)}/{len(task_titles)} completed

## Implementation Overview

{spec_info.get('description', 'This specification has been successfully implemented.')}

## Completed Tasks

"""
    
    for i, task_title in enumerate(task_titles, 1):
        content += f"{i}. ✅ {task_title}\n"
    
    content += f"""

## Key Deliverables

The implementation includes all required functionality as specified in the requirements document.

## Files Created/Modified

*Note: Specific file details should be documented here based on the implementation.*

## Configuration Requirements

*Note: Any environment variables or configuration needed should be documented here.*

## Future Enhancement Opportunities

*Note: Potential future improvements can be listed here.*

## Handoff Notes

This specification is complete and ready for production use. Refer to the requirements and design documents for detailed information about the implementation.

---
*This summary was automatically generated by the Spec Completion Monitor agent hook on {completion_date}.*
"""
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"📋 Created completion summary: {summary_file}")


def check_spec_completion(spec_dir: str) -> bool:
    """
    Check if a spec is completed and create completion files if needed.
    
    Returns:
        True if spec was completed and files were created, False otherwise
    """
    tasks_file = os.path.join(spec_dir, 'tasks.md')
    completion_file = os.path.join(spec_dir, '.completed')
    
    # Skip if completion file already exists
    if os.path.exists(completion_file):
        print(f"⏭️  Spec already marked as completed: {spec_dir}")
        return False
    
    # Parse tasks
    total_tasks, completed_tasks, task_titles = parse_tasks_file(tasks_file)
    
    if total_tasks == 0:
        print(f"⚠️  No tasks found in: {tasks_file}")
        return False
    
    print(f"📊 Spec status: {completed_tasks}/{total_tasks} tasks completed")
    
    # Check if all tasks are completed
    if completed_tasks == total_tasks:
        print(f"🎉 All tasks completed in spec: {os.path.basename(spec_dir)}")
        
        # Get spec information
        spec_info = get_spec_info(spec_dir)
        
        # Create completion files
        create_completion_file(spec_dir, total_tasks, completed_tasks, task_titles, spec_info)
        create_completion_summary(spec_dir, spec_info, task_titles)
        
        return True
    else:
        remaining = total_tasks - completed_tasks
        print(f"⏳ Spec not yet complete: {remaining} tasks remaining")
        return False


def main():
    """Main entry point for the agent hook."""
    if len(sys.argv) != 2:
        print("❌ Invalid number of arguments")
        print("Usage:")
        print("  python spec-completion-agent.py <spec_directory>")
        print("  python spec-completion-agent.py --scan-all")
        sys.exit(1)
    # …rest of main() follows…
    
    if sys.argv[1] == '--scan-all':
        # Scan all specs in .kiro/specs/
        specs_dir = '.kiro/specs'
        try:
            spec_names = os.listdir(specs_dir)
        except FileNotFoundError:
            print(f"❌ Specs directory not found: {specs_dir}")
            sys.exit(1)
        except PermissionError:
            print(f"❌ Permission denied accessing specs directory: {specs_dir}")
            sys.exit(1)
        except OSError as e:
            print(f"❌ Error reading specs directory: {e}")
            sys.exit(1)
        try:
        try:
            spec_names = os.listdir(specs_dir)
        except OSError as e:
            print(f"❌ Error reading specs directory: {e}")
            sys.exit(1)
        
        for spec_name in spec_names:
            spec_path = os.path.join(specs_dir, spec_name)
            if os.path.isdir(spec_path):
                print(f"\n🔍 Checking spec: {spec_name}")
                try:
                    if check_spec_completion(spec_path):
                        completed_count += 1
                except Exception as e:
                    print(f"⚠️  Error checking spec {spec_name}: {e}")
        
        print(f"\n✨ Scan complete: {completed_count} specs marked as completed")
    else:
        # Check specific spec directory
        spec_dir = sys.argv[1]
        if not os.path.exists(spec_dir):
            print(f"❌ Spec directory not found: {spec_dir}")
            sys.exit(1)
        
        print(f"🔍 Checking spec completion: {spec_dir}")
        if check_spec_completion(spec_dir):
            print("✨ Spec completion processing complete!")
        else:
            print("📝 Spec is not yet complete or already processed")


if __name__ == '__main__':
    main()