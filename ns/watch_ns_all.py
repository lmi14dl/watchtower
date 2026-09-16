#!/usr/bin/env python3
import sys, os, subprocess, tempfile, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from database.db import *


def run_command_in_bash(command):
    try:
        result = subprocess.run(["bash", "-c", command], capture_output=True, text=True)

        if result.returncode != 0:
            print("Error occured:", result.stderr)
            return False

        return result.stdout.splitlines()
        
    except subprocess.CalledProcessError as exc:
        print("Status: FAIL", exc.returncode, exc.output)

def create_tempfile(data):
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_file:
        temp_file.write(data)
        return temp_file.name

class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"

def dnsx(subdomains_array, domain):
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_file:
        for sub in subdomains_array:
            temp_file.write(sub + "\n")

    subdomains_file = temp_file.name
    command = f"shuffledns -l {subdomains_file} -silent -d {domain} -mode resolve -r {config()['RESOLVERS_PATH']} -t 10 | dnsx -silent -resp -json -r {config()['RESOLVERS_PATH']}"

    print(f"{colors.GRAY}Executing commands: {command}{colors.RESET}")
    results = run_command_in_bash(command)
    for res in results:
        # TODO: check if IP belongs to cdn or not, if yes then skip, if no add {'cdn':'cdn_name'}
        res = json.loads(res)
        upsert_lives({'subdomain':res['host'], 'domain':domain, 'ips': res.get('a',[]), 'cdn': None})

    return True

if __name__ == "__main__":

    programs = Programs.objects().all()

    for program in programs:
        for scope in program.scopes:
            obj_subs = Subdomains.objects(scope=scope)

            if obj_subs:
                print(f"[{current_time()}] Running DnsX module for {scope} subdoamins")
                dnsx([obj_sub.subdomain for obj_sub in obj_subs], scope)
                
                    
                #     upsert_lives(obj_subs.program_name, sub, 'subfinder')
            else:
                print(f"[{current_time()}] scope {scope} does not exist!")


