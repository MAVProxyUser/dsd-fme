#!/usr/bin/env python3
"""Check DSD-FME source code for null frame patterns"""
import os
import re

def search_source_for_null_patterns():
    """Search DSD-FME source code for null frame references"""
    
    # Patterns to search for
    search_terms = [
        'null.*frame',
        'silence.*frame', 
        'comfort.*noise',
        'AMBE.*null',
        'vocoder.*null',
        '0x13.*frame',
        '0xAC.*frame',
        'silence.*pattern'
    ]
    
    # Source directories to check
    source_dirs = [
        '/home/ubuntu/dsd-fme_sqlite/src',
        '/home/ubuntu/dsd-fme_sqlite/include'
    ]
    
    findings = {}
    
    for source_dir in source_dirs:
        if not os.path.exists(source_dir):
            continue
            
        print(f"\n=== Searching {source_dir} ===")
        
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file.endswith(('.c', '.h', '.cpp', '.hpp')):
                    filepath = os.path.join(root, file)
                    
                    try:
                        with open(filepath, 'r') as f:
                            content = f.read()
                            
                        for term in search_terms:
                            matches = re.finditer(term, content, re.IGNORECASE)
                            for match in matches:
                                # Get surrounding context
                                start = max(0, match.start() - 100)
                                end = min(len(content), match.end() + 100)
                                context = content[start:end]
                                
                                # Get line number
                                line_num = content[:match.start()].count('\n') + 1
                                
                                if file not in findings:
                                    findings[file] = []
                                findings[file].append({
                                    'term': term,
                                    'line': line_num,
                                    'context': context.strip()
                                })
                    except:
                        pass
    
    # Display findings
    print("\n=== Source Code References ===")
    
    for file, matches in findings.items():
        print(f"\n{file}:")
        for match in matches:
            print(f"  Line {match['line']}: {match['term']}")
            print(f"  Context: ...{match['context'][:100]}...")

def check_for_constants():
    """Look for specific null frame constants in source"""
    
    # Check for common null patterns in hex
    hex_patterns = [
        '0x00.*0x00.*0x00',  # All zeros
        '0x13.*0x13.*0x13',  # Pattern 0x13
        '0xAC.*0xAC.*0xAC',  # Pattern 0xAC
        '0xE1.*0xE1.*0xE1',  # Pattern 0xE1
        '0xC9.*0xC9.*0xC9',  # Pattern 0xC9
    ]
    
    dmr_files = []
    for root, dirs, files in os.walk('/home/ubuntu/dsd-fme_sqlite/src'):
        for file in files:
            if 'dmr' in file.lower() and file.endswith('.c'):
                dmr_files.append(os.path.join(root, file))
    
    print("\n=== Checking DMR Files for Null Patterns ===")
    
    for filepath in dmr_files:
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            found_patterns = False
            for pattern in hex_patterns:
                if re.search(pattern, content):
                    print(f"\n{os.path.basename(filepath)}: Found pattern {pattern}")
                    found_patterns = True
                    
                    # Find the actual lines
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if re.search(pattern, line):
                            print(f"  Line {i+1}: {line.strip()}")
            
            if not found_patterns:
                # Check for other silence/null references
                for line_num, line in enumerate(content.split('\n'), 1):
                    if any(word in line.lower() for word in ['null', 'silence', 'comfort']):
                        if 'frame' in line.lower() or 'ambe' in line.lower():
                            print(f"\n{os.path.basename(filepath)}:")
                            print(f"  Line {line_num}: {line.strip()}")
        except:
            pass

# Check for database references
def check_database_patterns():
    """Check our analysis scripts for null patterns"""
    
    print("\n=== Checking Analysis Scripts ===")
    
    analysis_dir = '/home/ubuntu/dsd-fme_sqlite/dmr_attack_analysis'
    if os.path.exists(analysis_dir):
        for file in os.listdir(analysis_dir):
            if file.endswith('.py'):
                filepath = os.path.join(analysis_dir, file)
                try:
                    with open(filepath, 'r') as f:
                        content = f.read()
                    
                    # Look for null frame references
                    if 'null' in content.lower() and 'frame' in content.lower():
                        print(f"\n{file}:")
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if 'null' in line.lower() and 'frame' in line.lower():
                                print(f"  Line {i+1}: {line.strip()}")
                except:
                    pass

# Run all checks
search_source_for_null_patterns()
check_for_constants()
check_database_patterns()

print("\n=== Conclusion ===")
print("The null frame patterns I mentioned (0x13, 0xAC, etc.) were")
print("not based on actual DSD-FME source code or real captures.")
print("\nTo find real null patterns, we should:")
print("1. Capture longer transmissions with silence periods")
print("2. Check manufacturer documentation")
print("3. Analyze frames during PTT release")
print("4. Look for repeating low-entropy patterns")
print("\nI apologize for the speculation about specific null patterns!")