#!/usr/bin/env python3
"""
Unit tests for clean_mcp_response module
"""

import pytest
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.clean_mcp_response import clean_text_content, format_bitcoin_content


class TestCleanTextContent:
    """Test cases for the clean_text_content function"""

    def test_normalize_line_endings(self):
        """Test that line endings are normalized correctly"""
        # Test Windows line endings
        text_with_crlf = "Line 1\r\nLine 2\r\nLine 3"
        result = clean_text_content(text_with_crlf)
        assert "\r\n" not in result
        assert "Line 1\nLine 2\nLine 3" in result

    def test_camel_case_spacing(self):
        """Test that camelCase words get proper spacing"""
        text = "BitcoinBlockchain"
        result = clean_text_content(text)
        assert "Bitcoin Blockchain" in result

    def test_excessive_spaces_removal(self):
        """Test that excess_file__])n([_ytest.mai   p":
 "__main__e__ == f __nam"]


ilt["text resus great" inin iBitco"   assert 
     text"""] == "type result[ assert     )
  t(contentntentcoin_cormat_bifot = ul     resreat"}
   n    is    g"Bitcoit": "texext", e": "ttypt = {"   conten""
     ed"cleantent is  conextn tai pl"Test that      "":
  g(self)ext_cleaninlain_t def test_p   t

t == contenesul r  assert      ontent)
ontent(c_ct_bitcoinlt = forma      resu
  e.jpg"}le.com/imagttps://examp"hurl": "image", "": {"typecontent = 
        "hanged"" unchrough ts passedontent i non-text catTest th""       "):
 lf(seoughthrt_passconten_text_test_non  def 

  nction"""content fumat_bitcoin_e for th forsesest ca    """Tent:
tcoinContstFormatBiclass Te


() == resultt.striprt resul  asse0
      esult) > (r len asserted
       erly cleanuld be prop  # Shot
      resuln" not in "\\ssert  a      
 ines newlscapedot contain e nld # Shou   
       t)
     complex_texnt(_conte clean_text   result =  
     ."
      ent directlys to be s\npaymentws online\lom that al cash systetronicpeer elec-to-is a peer"Bitcoin = omplex_text       ces"""
  tiple issu mul that has-like textx PDF complet with  """Tes:
      (self)ext_pdf_texf test_compl de"

   result == "    assert     t("")
ext_contenclean_tult =       res"""
  ectlyndled corrring is hampty st ethatest   """T      
g(self):pty_strin def test_em
   lt
resurency" in a cryptocurcoin is it"B  assert    ext)
   (tnt_contetext= clean_lt    resu
     ncy"ocurre crypt  a     is  oin  Bitc = "    text"
    aces"" single spe reduced to arive spaces