#!/usr/bin/env python3
"""Tests unitaires pour la couche de cache intelligent http_cache.py"""
from __future__ import annotations
import sys, os, json, time, tempfile, unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import http_cache


class TestRateLimiter(unittest.TestCase):
    """Test du RateLimiter."""
    
    def test_initialization(self):
        """Test de l'initialisation."""
        limiter = http_cache.RateLimiter(max_calls=5, period=10)
        self.assertEqual(limiter.max_calls, 5)
        self.assertEqual(limiter.period, 10)
        self.assertEqual(len(limiter._timestamps), 0)
    
    @patch("time.sleep")
    @patch("time.time")
    def test_wait_no_limit(self, mock_time, mock_sleep):
        """Test que wait ne bloque pas tant que la limite n'est pas atteinte."""
        mock_time.return_value = 1000.0
        limiter = http_cache.RateLimiter(max_calls=3, period=10)
        
        limiter.wait()
        self.assertEqual(len(limiter._timestamps), 1)
        mock_sleep.assert_not_called()
        
        limiter.wait()
        limiter.wait()
        self.assertEqual(len(limiter._timestamps), 3)
        mock_sleep.assert_not_called()


class TestHttpCache(unittest.TestCase):
    """Test du système de cache intelligent."""
    
    def setUp(self):
        """Préparation des tests."""
        # Créer un répertoire temporaire pour le cache
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_cache_dir = http_cache.CACHE_DIR
        http_cache.CACHE_DIR = self.temp_dir.name
    
    def tearDown(self):
        """Nettoyage après les tests."""
        self.temp_dir.cleanup()
        http_cache.CACHE_DIR = self.original_cache_dir
    
    def test_get_ttl_for_url(self):
        """Test de la détection automatique du TTL."""
        self.assertEqual(http_cache._get_ttl_for_url("https://example.com/live-scores"), http_cache.TTL_CONFIG["live"])
        self.assertEqual(http_cache._get_ttl_for_url("https://example.com/schedule"), http_cache.TTL_CONFIG["schedule"])
        self.assertEqual(http_cache._get_ttl_for_url("https://example.com/squads"), http_cache.TTL_CONFIG["squads"])
        self.assertEqual(http_cache._get_ttl_for_url("https://example.com/elo-ratings"), http_cache.TTL_CONFIG["ratings"])
        self.assertEqual(http_cache._get_ttl_for_url("https://example.com/stats"), http_cache.TTL_CONFIG["stats"])
        self.assertEqual(http_cache._get_ttl_for_url("https://example.com/unknown"), http_cache.TTL_CONFIG["default"])
    
    def test_clean_cache(self):
        """Test du nettoyage du cache."""
        # Créer des fichiers de cache test
        test_file1 = os.path.join(http_cache.CACHE_DIR, "test1.json")
        test_file2 = os.path.join(http_cache.CACHE_DIR, "test2.json")
        with open(test_file1, "w") as f:
            json.dump({"test": "data1"}, f)
        with open(test_file2, "w") as f:
            json.dump({"test": "data2"}, f)
        
        # Vérifier qu'ils existent
        self.assertTrue(os.path.exists(test_file1))
        self.assertTrue(os.path.exists(test_file2))
        
        # Simuler des fichiers vieux de 10 jours
        old_time = time.time() - (10 * 86400) - 100
        os.utime(test_file1, (old_time, old_time))
        
        # Nettoyer le cache (max 7 jours)
        deleted = http_cache.clean_cache(max_age_days=7)
        self.assertEqual(deleted, 1)
        self.assertFalse(os.path.exists(test_file1))
        self.assertTrue(os.path.exists(test_file2))
    
    def test_clear_cache(self):
        """Test de la suppression complète du cache."""
        test_file1 = os.path.join(http_cache.CACHE_DIR, "test1.json")
        with open(test_file1, "w") as f:
            json.dump({"test": "data1"}, f)
        self.assertTrue(os.path.exists(test_file1))
        http_cache.clear_cache()
        self.assertFalse(os.path.exists(test_file1))


if __name__ == "__main__":
    unittest.main()
