# configuration, variables, etc
import os

def config():
    return {
        'WATCH_DIR': os.path.dirname(os.path.abspath(__file__)),
        'RESOLVERS_PATH': os.environ.get('RESOLVERS_PATH', '/app/config/resolvers/resolvers.txt'),
        'GAU_CONFIG': os.environ.get('GAU_CONFIG', '/app/config/gau-config/.gau.toml'),
        'WEBHOOK_URL': os.environ.get('DISCORD_WEBHOOK_URL', ''),
        'DNS_BRUTE_WORDLIST': os.environ.get('DNS_BRUTE_WORDLIST', '/app/config/wordlists/words-merged.txt'),
    }
