"""
Tests for quote preservation in QuoteCleaner.
"""
import pytest
from digest_core.normalize.quotes import QuoteCleaner


class TestQuotePreservation:
    """Test suite for top-level quote preservation."""
    
    def test_inline_reply_with_task_preserved(self):
        """Test that task/instruction in top-level quote is preserved."""
        email_text = """Hi team,

I need this done by Friday.

On Mon, Dec 4, 2023 at 10:30 AM John Doe <john@example.com> wrote:
> Please review the attached proposal and provide feedback.
> We need your approval by end of week.
>
> Let me know if you have any questions.

Thanks,
Boss"""
        
        cleaner = QuoteCleaner(keep_top_quote_head=True)
        result = cleaner.clean_quotes(email_text)
        
        # Check that top quote is preserved with marker
        assert '[Quoted head retained]' in result
        assert '> Please review the attached proposal' in result
        assert '> We need your approval by end of week.' in result
        
        # Check that original content is present
        assert 'I need this done by Friday' in result
        assert 'Thanks,' in result
        assert 'Boss' in result
    
    def test_multilevel_quotes_only_top_preserved(self):
        """Test that only top-level quote is kept, deep quotes removed."""
        email_text = """Agreed, let's proceed.

From: Alice <alice@example.com>
> I think we should go ahead with option B.
>
> > What do you think about option A vs B?
> >
> > > Original proposal was for option C.

Regards"""
        
        cleaner = QuoteCleaner(keep_top_quote_head=True)
        result = cleaner.clean_quotes(email_text)
        
        # Top-level quote preserved
        assert '[Quoted head retained]' in result
        assert '> I think we should go ahead with option B.' in result
        
        # Deep quotes (>> and >>>) should be removed
        assert '> >' not in result
        assert 'option A vs B' not in result
        assert 'option C' not in result
    
    def test_legacy_mode_removes_all_quotes(self):
        """Test that legacy mode (keep_top_quote_head=False) removes all quotes."""
        email_text = """New reply here.

On Mon Dec 4 2023 John wrote:
> Original message content.
> Second line of original.

End of email."""
        
        cleaner = QuoteCleaner(keep_top_quote_head=False)
        result = cleaner.clean_quotes(email_text)
        
        # No quotes preserved
        assert '[Quoted head retained]' not in result
        assert 'Original message content' not in result
        assert 'Second line of original' not in result
        
        # Only new content
        assert 'New reply here' in result
        assert 'End of email' in result
    
    def test_russian_quote_header_preserved(self):
        """Test Russian quote headers (От:, Дата:) are recognized."""
        email_text = """Согласен, делаем так.

От: Иванов Иван
Дата: 4 декабря 2023
> Прошу согласовать бюджет на следующий квартал.
> Срок: до пятницы.

Спасибо."""
        
        cleaner = QuoteCleaner(keep_top_quote_head=True)
        result = cleaner.clean_quotes(email_text)
        
        assert '[Quoted head retained]' in result
        assert '> Прошу согласовать бюджет' in result
        assert '> Срок: до пятницы.' in result
    
    def test_quote_truncation_after_2_paragraphs(self):
        """Test that quote is truncated after 2 paragraphs."""
        email_text = """Got it.

On Mon Dec 4 wrote:
> Paragraph 1: First important point here.
>
> Paragraph 2: Second important point.
>
> Paragraph 3: This should be removed.
>
> Paragraph 4: This too.

Thanks."""
        
        cleaner = QuoteCleaner(keep_top_quote_head=True)
        result = cleaner.clean_quotes(email_text)
        
        # First 2 paragraphs preserved
        assert '> Paragraph 1: First important point here.' in result
        assert '> Paragraph 2: Second important point.' in result
        
        # Paragraphs 3-4 removed
        assert 'Paragraph 3' not in result
        assert 'Paragraph 4' not in result
    
    def test_quote_truncation_after_10_lines(self):
        """Test that quote is truncated after 10 lines."""
        quote_lines = '\n'.join([f'> Line {i+1} of quoted content.' for i in range(15)])
        email_text = f"""Reply here.

On Mon wrote:
{quote_lines}

End."""
        
        cleaner = QuoteCleaner(keep_top_quote_head=True)
        result = cleaner.clean_quotes(email_text)
        
        # Some lines preserved
        assert '> Line 1 of quoted content.' in result
        assert '> Line 5 of quoted content.' in result
        
        # Lines beyond 10 should be removed
        assert 'Line 15 of quoted content' not in result
    
    def test_no_quotes_no_marker_added(self):
        """Test that emails without quotes don't get markers."""
        email_text = """Just a simple email.

No quotes here at all.

Regards,
John"""
        
        cleaner = QuoteCleaner(keep_top_quote_head=True)
        result = cleaner.clean_quotes(email_text)
        
        assert '[Quoted head retained]' not in result
        assert result.strip() == email_text.strip()
    
    def test_forward_marker_triggers_deep_quote(self):
        """Test that -----Original Message----- triggers deep quote removal."""
        email_text = """FYI, see below.

-----Original Message-----
From: sender@example.com
Sent: Monday, December 4, 2023
To: recipient@example.com
Subject: Important

This should be removed as deep quote.

Thanks."""
        
        cleaner = QuoteCleaner(keep_top_quote_head=True)
        result = cleaner.clean_quotes(email_text)
        
        # Deep quote removed
        assert 'Original Message' not in result
        assert 'This should be removed' not in result
        
        # Top content preserved
        assert 'FYI, see below' in result
    
    def test_quote_length_growth_minimal(self):
        """Test that preserved quotes don't significantly increase text length."""
        # Email with moderate top quote
        email_text = """Action: Please approve this.

On Mon wrote:
> Requesting approval for budget allocation.
> Amount: $50,000 for Q1 2024.

Thanks!"""
        
        cleaner = QuoteCleaner(keep_top_quote_head=True)
        result = cleaner.clean_quotes(email_text)
        
        # Calculate length growth
        original_len = len(email_text)
        result_len = len(result)
        growth = (result_len - original_len) / original_len
        
        # Growth should be minimal (mostly from marker "[Quoted head retained]")
        assert growth < 0.15  # Less than 15% growth
        
        # But content should be preserved
        assert '> Requesting approval' in result


class TestQuoteCleaningEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_empty_text(self):
        """Test handling of empty text."""
        cleaner = QuoteCleaner(keep_top_quote_head=True)
        assert cleaner.clean_quotes('') == ''
        assert cleaner.clean_quotes(None) == None
    
    def test_only_quote_no_reply(self):
        """Test email that is only a quote (forward without comment)."""
        email_text = """On Mon wrote:
> This is the entire content.
> No reply above."""
        
        cleaner = QuoteCleaner(keep_top_quote_head=True)
        result = cleaner.clean_quotes(email_text)
        
        # Top quote preserved even if it's all there is
        assert '[Quoted head retained]' in result
        assert '> This is the entire content.' in result
    
    def test_signature_removal_still_works(self):
        """Test that signature removal still works with quote preservation."""
        email_text = """Let's do it.

On Mon wrote:
> Original request here.

Best regards,
John Doe
Sent from my iPhone"""
        
        cleaner = QuoteCleaner(keep_top_quote_head=True)
        result = cleaner.clean_quotes(email_text)
        
        # Quote preserved
        assert '> Original request here.' in result
        
        # Signature removed
        assert 'Sent from my iPhone' not in result
        assert 'Best regards' not in result  # Signature pattern matched

