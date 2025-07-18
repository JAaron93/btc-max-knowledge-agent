import requests
import feedparser
from bs4 import BeautifulSoup
from newspaper import Article
import time
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse
import json

class BitcoinDataCollector:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        # Bitcoin and blockchain sources
        self.sources = {
            'bitcoin_org': 'https://bitcoin.org/en/',
            'lightning_network': 'https://lightning.network/',
            'bitcoin_wiki': 'https://en.bitcoin.it/wiki/Main_Page',
            'coindesk_bitcoin': 'https://www.coindesk.com/tag/bitcoin/',
            'cointelegraph_bitcoin': 'https://cointelegraph.com/tags/bitcoin',
            'bitcoin_magazine': 'https://bitcoinmagazine.com/',
        }
        
        # RSS feeds for news
        self.rss_feeds = [
            'https://bitcoinmagazine.com/feed',
            'https://www.coindesk.com/arc/outboundfeeds/rss/',
            'https://cointelegraph.com/rss',
        ]
    
    def collect_from_rss(self, max_articles: int = 20) -> List[Dict[str, Any]]:
        """Collect articles from RSS feeds"""
        articles = []
        
        for feed_url in self.rss_feeds:
            try:
                print(f"Fetching RSS feed: {feed_url}")
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:max_articles]:
                    try:
                        article = Article(entry.link)
                        article.download()
                        article.parse()
                        
                        if len(article.text) > 500:  # Only include substantial articles
                            articles.append({
                                'id': f"rss_{len(articles)}",
                                'title': entry.title,
                                'content': article.text,
                                'source': feed_url,
                                'category': 'news',
                                'url': entry.link,
                                'published': entry.get('published', '')
                            })
                        
                        time.sleep(1)  # Be respectful
                        
                    except Exception as e:
                        print(f"Error processing article {entry.link}: {e}")
                        continue
                        
            except Exception as e:
                print(f"Error fetching RSS feed {feed_url}: {e}")
                continue
        
        return articles
    
    def collect_bitcoin_basics(self) -> List[Dict[str, Any]]:
        """Collect basic Bitcoin information"""
        documents = []
        
        # Bitcoin whitepaper content (simplified)
        bitcoin_whitepaper = {
            'id': 'bitcoin_whitepaper',
            'title': 'Bitcoin: A Peer-to-Peer Electronic Cash System',
            'content': """Bitcoin is a peer-to-peer electronic cash system that allows online payments to be sent directly from one party to another without going through a financial institution. Digital signatures provide part of the solution, but the main benefits are lost if a trusted third party is still required to prevent double-spending. We propose a solution to the double-spending problem using a peer-to-peer network. The network timestamps transactions by hashing them into an ongoing chain of hash-based proof-of-work, forming a record that cannot be changed without redoing the proof-of-work. The longest chain not only serves as proof of the sequence of events witnessed, but proof that it came from the largest pool of CPU power.""",
            'source': 'bitcoin.org',
            'category': 'fundamentals'
        }
        documents.append(bitcoin_whitepaper)
        
        # Lightning Network basics
        lightning_basics = {
            'id': 'lightning_network_basics',
            'title': 'Lightning Network Overview',
            'content': """The Lightning Network is a "Layer 2" payment protocol layered on top of Bitcoin. It enables fast transactions between participating nodes and has been proposed as a solution to the bitcoin scalability problem. It features a peer-to-peer system for making micropayments of cryptocurrency through a network of bidirectional payment channels without delegating custody of funds. Normal use of the Lightning Network consists of opening a payment channel by committing a funding transaction to the relevant base blockchain, followed by making any number of Lightning Network transactions that update the tentative distribution of the channel's funds without broadcasting those to the blockchain, optionally followed by closing the payment channel by broadcasting the final version of the settlement transaction to distribute the channel's funds.""",
            'source': 'lightning.network',
            'category': 'layer2'
        }
        documents.append(lightning_basics)
        
        # Blockchain basics
        blockchain_basics = {
            'id': 'blockchain_basics',
            'title': 'Understanding Blockchain Technology',
            'content': """A blockchain is a distributed ledger with growing lists of records, called blocks, that are linked and secured using cryptography. Each block contains a cryptographic hash of the previous block, a timestamp, and transaction data. By design, a blockchain is resistant to modification of its data. This is because once recorded, the data in any given block cannot be altered retroactively without altering all subsequent blocks. For use as a distributed ledger, a blockchain is typically managed by a peer-to-peer network for use as a publicly distributed ledger, where nodes collectively adhere to a protocol to communicate and validate new blocks.""",
            'source': 'educational',
            'category': 'fundamentals'
        }
        documents.append(blockchain_basics)
        
        return documents
    
    def collect_genius_act_info(self) -> List[Dict[str, Any]]:
        """Collect information about the GENIUS Act"""
        documents = []
        
        genius_act_overview = {
            'id': 'genius_act_overview',
            'title': 'GENIUS Act - Blockchain Innovation',
            'content': """The GENIUS Act (Generating Entrepreneurial Networks to Improve Understanding and Success) is legislation aimed at promoting blockchain technology innovation and cryptocurrency adoption in the United States. The act focuses on creating regulatory clarity for blockchain businesses, supporting research and development in distributed ledger technologies, and fostering innovation in the digital asset space. It aims to position the United States as a leader in blockchain technology while ensuring consumer protection and maintaining financial stability.""",
            'source': 'legislative',
            'category': 'regulation'
        }
        documents.append(genius_act_overview)
        
        return documents
    
    def collect_dapp_information(self) -> List[Dict[str, Any]]:
        """Collect information about decentralized applications"""
        documents = []
        
        dapp_basics = {
            'id': 'dapp_basics',
            'title': 'Decentralized Applications (dApps) Overview',
            'content': """Decentralized applications (dApps) are digital applications that run on a blockchain or peer-to-peer network of computers instead of a single computer. dApps are outside the purview and control of a single authority. dApps can be developed for a variety of purposes including gaming, finance, and social media. The key characteristics of dApps include: decentralization (no single point of failure), open source code, cryptographic security, and token incentives. Popular dApp categories include DeFi (Decentralized Finance), NFT marketplaces, gaming platforms, and social networks.""",
            'source': 'educational',
            'category': 'dapps'
        }
        documents.append(dapp_basics)
        
        return documents
    
    def collect_all_documents(self, max_news_articles: int = 30) -> List[Dict[str, Any]]:
        """Collect all documents from various sources"""
        all_documents = []
        
        print("Collecting Bitcoin basics...")
        all_documents.extend(self.collect_bitcoin_basics())
        
        print("Collecting GENIUS Act information...")
        all_documents.extend(self.collect_genius_act_info())
        
        print("Collecting dApp information...")
        all_documents.extend(self.collect_dapp_information())
        
        print("Collecting news articles...")
        all_documents.extend(self.collect_from_rss(max_news_articles))
        
        print(f"Total documents collected: {len(all_documents)}")
        return all_documents
    
    def save_documents(self, documents: List[Dict[str, Any]], filename: str = "bitcoin_documents.json"):
        """Save documents to JSON file"""
        with open(f"data/{filename}", 'w', encoding='utf-8') as f:
            json.dump(documents, f, indent=2, ensure_ascii=False)
        print(f"Documents saved to data/{filename}")
    
    def load_documents(self, filename: str = "bitcoin_documents.json") -> List[Dict[str, Any]]:
        """Load documents from JSON file"""
        try:
            with open(f"data/{filename}", 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"File data/{filename} not found")
            return []