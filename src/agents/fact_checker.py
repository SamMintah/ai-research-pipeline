from typing import Dict, Any, List, Tuple
import json
from datetime import datetime, timedelta
from src.agents.base import BaseAgent
from src.models import Company, Claim, Source, ClaimSource
from src.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import and_

class FactCheckerAgent(BaseAgent):
    """Agent for fact-checking and cross-referencing claims"""
    
    def __init__(self):
        super().__init__()
        self.min_sources_required = 2
        self.confidence_threshold = 0.7
        self.date_tolerance_days = 30
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fact-check all claims for a company"""
        company_slug = input_data.get("company_slug")
        if not company_slug:
            return {"error": "Company slug required"}
        
        try:
            # Get all claims for the company
            claims_data = await self._get_company_claims(company_slug)
            if not claims_data:
                return {"error": "No claims found for company"}
            
            # Cross-reference claims
            verification_results = await self.batch_check_facts(claims_data["claims"], claims_data["sources"])
            
            # Update database with verification results
            await self._update_claim_verification(verification_results)
            
            # Generate fact-check report
            report = self._generate_fact_check_report(verification_results)
            
            return {
                "company_slug": company_slug,
                "total_claims": len(verification_results),
                "verified_claims": len([v for v in verification_results if v.get("verified", False)]),
                "flagged_claims": len([v for v in verification_results if v.get("flagged", False)]),
                "verification_results": verification_results,
                "report": report,
                "checked_at": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            print(f"Fact checker process error: {e}")
            return {
                "error": f"Fact checking failed: {str(e)}",
                "company_slug": company_slug,
                "total_claims": 0,
                "verified_claims": 0,
                "flagged_claims": 0,
                "verification_results": [],
                "report": "# Fact-Check Report\n\nFact-checking failed due to processing error.",
                "checked_at": datetime.utcnow().isoformat()
            }


    async def batch_check_facts(self, claims: List[Dict[str, Any]], sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Batch verify multiple claims against available sources using a single LLM call for initial verification."""
        
        # Prepare batched prompt for initial verification
        batched_prompt_parts = []
        for i, claim in enumerate(claims):
            claim_text = claim.get("claim", "")
            claim_date = claim.get("claim_date")
            
            # Include relevant sources for each claim in the prompt
            # For true batching, we need to decide how to present sources for multiple claims.
            # For now, let's just include a general instruction about sources.
            
            batched_prompt_parts.append(f"Claim {i+1}:\nClaim Text: \"{claim_text}\"\nClaim Date: {claim_date if claim_date else 'N/A'}\n")
            
        # Add all sources to the prompt, as they might be relevant to multiple claims
        sources_text = "\n\n".join([f"Source {s['id']}: {s['title']} ({s['url']})\nContent: {s['content'][:1000]}..." for s in sources]) # Limit source content to avoid exceeding token limits
        
        # Fix the f-string issue by using a separate variable for the join
        claims_text = '\n'.join(batched_prompt_parts)
        
        full_prompt = f"""You are a fact-checking AI. Your task is to verify a list of claims against the provided sources.
For each claim, determine if it is SUPPORTED, UNSUPPORTED, or REQUIRES_MORE_INFO based on the given sources.
Also, identify if there are any contradictions within the sources for each claim.

Here are the claims to verify:

{claims_text}

Here are the available sources:

{sources_text}

For each claim, provide a JSON object with the following structure:
{{
    "claim_id": "ID of the claim",
    "claim": "The original claim text",
    "status": "SUPPORTED" | "UNSUPPORTED" | "REQUIRES_MORE_INFO",
    "contradiction_found": true | false,
    "reasoning": "Brief explanation for the status and contradiction_found"
}}

Return a JSON array of these objects, one for each claim. Ensure the output is valid JSON.
"""
        messages = [{"role": "user", "content": full_prompt}]
        
        try:
            batched_response = await self.call_llm(messages, temperature=0.1)
            if not batched_response or not batched_response.strip():
                raise ValueError("Empty LLM response")
            
            # Clean up markdown formatting if present
            cleaned_response = batched_response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]  # Remove ```json
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]   # Remove ```
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]  # Remove trailing ```
            cleaned_response = cleaned_response.strip()
            
            initial_verification_results = json.loads(cleaned_response)
        except Exception as e:
            print(f"Error parsing batched LLM response: {e}")
            print(f"Raw LLM response: {batched_response[:200] if batched_response else 'None'}...")
            # Fallback to individual verification if batching fails
            initial_verification_results = []
            for claim in claims:
                initial_verification_results.append({
                    "claim_id": claim.get("id"),
                    "claim": claim.get("claim"),
                    "status": "REQUIRES_MORE_INFO",
                    "contradiction_found": False,
                    "reasoning": "Batch verification failed or parse error."
                })
            # Return the fallback results with proper structure for final processing
            fallback_results = []
            for fallback_result in initial_verification_results:
                claim_id = fallback_result.get("claim_id")
                original_claim = next((c for c in claims if c.get("id") == claim_id), None)
                
                if original_claim:
                    fallback_results.append({
                        "claim_id": claim_id,
                        "claim": fallback_result.get("claim", "Unknown Claim"),
                        "verified": False,
                        "flagged": True,
                        "verification_score": 0.1,
                        "supporting_sources_count": 0,
                        "supporting_sources": [],
                        "date_consistency": {"consistent": False, "note": "Fallback due to LLM error"},
                        "contradictions": [],
                        "recommendation": "MANUAL_REVIEW_REQUIRED - LLM processing failed"
                    })
                else:
                    fallback_results.append({
                        "claim_id": claim_id,
                        "claim": fallback_result.get("claim", "Unknown Claim"),
                        "verified": False,
                        "flagged": True,
                        "verification_score": 0.0,
                        "supporting_sources_count": 0,
                        "supporting_sources": [],
                        "date_consistency": {"consistent": False, "note": "Claim not found"},
                        "contradictions": [],
                        "recommendation": "MANUAL_REVIEW_REQUIRED - Claim ID mismatch"
                    })
            return fallback_results

        final_verification_results = []
        for initial_result in initial_verification_results:
            claim_id = initial_result.get("claim_id")
            original_claim = next((c for c in claims if c.get("id") == claim_id), None)
            
            if original_claim:
                try:
                    # Now, perform the more detailed checks for each claim individually
                    verification = await self._verify_claim_detailed(original_claim, sources, initial_result)
                    final_verification_results.append(verification)
                except Exception as e:
                    print(f"Error in detailed verification for claim {claim_id}: {e}")
                    # Add fallback verification result
                    final_verification_results.append({
                        "claim_id": claim_id,
                        "claim": original_claim.get("claim", "Unknown Claim"),
                        "verified": False,
                        "flagged": True,
                        "verification_score": 0.0,
                        "supporting_sources_count": 0,
                        "supporting_sources": [],
                        "date_consistency": {"consistent": False, "note": "Detailed verification failed"},
                        "contradictions": [],
                        "recommendation": "MANUAL_REVIEW_REQUIRED - Processing error"
                    })
            else:
                print(f"Warning: Claim with ID {claim_id} not found in original claims list.")
                final_verification_results.append({
                    "claim_id": claim_id,
                    "claim": initial_result.get("claim", "Unknown Claim"),
                    "verified": False,
                    "flagged": True,
                    "verification_score": 0.0,
                    "supporting_sources_count": 0,
                    "supporting_sources": [],
                    "date_consistency": {"consistent": False, "note": "Claim not_found"},
                    "contradictions": [],
                    "recommendation": "MANUAL_REVIEW_REQUIRED - Claim ID mismatch"
                })
        
        return final_verification_results
    
    async def _get_company_claims(self, company_slug: str) -> Dict[str, Any]:
        """Get all claims and sources for a company"""
        db = next(get_db())
        
        try:
            company = db.query(Company).filter(Company.slug == company_slug).first()
            if not company:
                return None
            
            claims = db.query(Claim).filter(Claim.company_id == company.id).all()
            sources = db.query(Source).filter(Source.company_id == company.id).all()
            
            claims_data = []
            for claim in claims:
                claims_data.append({
                    "id": str(claim.id),
                    "claim": claim.claim,
                    "claim_date": claim.claim_date.isoformat() if claim.claim_date else None,
                    "subject": claim.subject,
                    "predicate": claim.predicate,
                    "object": claim.object,
                    "confidence": claim.confidence,
                    "corroboration_count": claim.corroboration_count
                })
            
            sources_data = []
            for source in sources:
                sources_data.append({
                    "id": str(source.id),
                    "url": source.url,
                    "domain": source.domain,
                    "title": source.title,
                    "content": source.content,
                    "reliability": source.reliability,
                    "published_at": source.published_at.isoformat() if source.published_at else None
                })
            
            return {
                "company": {"name": company.name, "slug": company.slug},
                "claims": claims_data,
                "sources": sources_data
            }
            
        finally:
            db.close()  
  
    async def _verify_claim_detailed(self, claim: Dict[str, Any], 
                                  sources: List[Dict[str, Any]], 
                                  initial_llm_result: Dict[str, Any]) -> Dict[str, Any]:
        """Verify a single claim against available sources"""
        claim_text = claim.get("claim", "")
        claim_date = claim.get("claim_date")
        
        # Find supporting sources
        supporting_sources = await self._find_supporting_sources(claim_text, sources)
        
        # Check date consistency
        date_consistency = await self._check_date_consistency(claim_date, supporting_sources)
        
        # Calculate verification score
        verification_score = self._calculate_verification_score(
            supporting_sources, date_consistency, claim.get("confidence", 0)
        )
        
        # Determine verification status based on initial LLM result and detailed checks
        verified = initial_llm_result.get("status") == "SUPPORTED" and \
                   verification_score >= self.confidence_threshold and \
                   len(supporting_sources) >= self.min_sources_required
        flagged = initial_llm_result.get("status") == "UNSUPPORTED" or \
                  verification_score < 0.5 or \
                  len(supporting_sources) < 1
        
        # Check for contradictions (from initial LLM result and detailed check)
        contradictions = []
        if initial_llm_result.get("contradiction_found", False):
            contradictions.append({"reasoning": initial_llm_result.get("reasoning", "Contradiction indicated by initial LLM check.")})
        
        detailed_contradictions = await self._find_contradictions(claim_text, sources)
        contradictions.extend(detailed_contradictions)
        
        return {
            "claim_id": claim.get("id"),
            "claim": claim_text,
            "verified": verified,
            "flagged": flagged,
            "verification_score": verification_score,
            "supporting_sources_count": len(supporting_sources),
            "supporting_sources": supporting_sources,
            "date_consistency": date_consistency,
            "contradictions": contradictions,
            "recommendation": self._get_recommendation(verified, flagged, contradictions)
        }
    
    async def _find_supporting_sources(self, claim_text: str, 
                                     sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find sources that support the given claim"""
        supporting_sources = []
        
        # Use LLM to find supporting evidence
        for source in sources:
            content = source.get("content", "")
            if not content:
                continue
            
            support_check = await self._check_source_support(claim_text, content, source)
            if support_check.get("supports", False):
                supporting_sources.append({
                    "source_id": source.get("id"),
                    "url": source.get("url"),
                    "domain": source.get("domain"),
                    "title": source.get("title"),
                    "reliability": source.get("reliability", 1),
                    "support_strength": support_check.get("strength", 0.5),
                    "evidence_snippet": support_check.get("evidence", "")
                })
        
        # Sort by reliability and support strength
        supporting_sources.sort(
            key=lambda x: (x.get("reliability", 0) * x.get("support_strength", 0)), 
            reverse=True
        )
        
        return supporting_sources
    
    async def _check_source_support(self, claim: str, content: str, 
                                  source: Dict[str, Any]) -> Dict[str, Any]:
        """Check if a source supports a specific claim"""
        prompt = f"""Analyze if this source content supports the given claim.        
        Claim: \"{claim}\"        
        Source: {source.get('title', 'Unknown')} ({source.get('domain', 'Unknown')})
        Content excerpt: {content[:1500]}...
        
        Determine:
        1. Does this source support the claim? (true/false)
        2. How strong is the support? (0.0-1.0)
        3. What specific text supports the claim?
        
        Return JSON:
        {{
            "supports": true/false,
            "strength": 0.0-1.0,
            "evidence": "exact quote that supports the claim",
            "reasoning": "brief explanation"
        }}
        
        Be conservative - only return true if there's clear supporting evidence."""
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.1)
        
        try:
            # Clean markdown formatting
            cleaned_response = response.strip() if response else ""
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            return json.loads(cleaned_response)
        except:
            return {"supports": False, "strength": 0.0, "evidence": "", "reasoning": "Parse error"}
    
    async def _check_date_consistency(self, claim_date: str, 
                                    supporting_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check if dates are consistent across sources"""
        if not claim_date:
            return {"consistent": True, "note": "No date to verify"}
        
        try:
            claim_datetime = datetime.fromisoformat(claim_date)
        except:
            return {"consistent": False, "note": "Invalid claim date format"}
        
        date_matches = 0
        date_conflicts = 0
        
        for source in supporting_sources:
            evidence = source.get("evidence_snippet", "")
            if evidence:
                # Extract dates from evidence using LLM
                extracted_dates = await self._extract_dates_from_text(evidence)
                
                for date_str in extracted_dates:
                    try:
                        source_date = datetime.fromisoformat(date_str)
                        days_diff = abs((claim_datetime - source_date).days)
                        
                        if days_diff <= self.date_tolerance_days:
                            date_matches += 1
                        else:
                            date_conflicts += 1
                    except:
                        continue
        
        consistency_score = date_matches / max(date_matches + date_conflicts, 1)
        
        return {
            "consistent": consistency_score >= 0.7,
            "consistency_score": consistency_score,
            "matches": date_matches,
            "conflicts": date_conflicts
        }
    
    async def _extract_dates_from_text(self, text: str) -> List[str]:
        """Extract dates from text using LLM"""
        prompt = f"""Extract all dates mentioned in this text and convert to ISO format (YYYY-MM-DD).
        
        Text: \"{text}\"        
        Return JSON array of dates in ISO format. Only include specific dates, not relative terms.
        Example: [\"2020-03-15\", \"2021-12-01\"]
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.1)
        
        try:
            # Clean markdown formatting
            cleaned_response = response.strip() if response else ""
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            dates = json.loads(cleaned_response)
            return dates if isinstance(dates, list) else []
        except:
            return []
    
    async def _find_contradictions(self, claim_text: str, 
                                 sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find sources that contradict the claim"""
        contradictions = []
        
        for source in sources[:10]:  # Limit to avoid too many API calls
            content = source.get("content", "")
            if not content:
                continue
            
            contradiction_check = await self._check_contradiction(claim_text, content, source)
            if contradiction_check.get("contradicts", False):
                contradictions.append({
                    "source_id": source.get("id"),
                    "url": source.get("url"),
                    "title": source.get("title"),
                    "contradiction_strength": contradiction_check.get("strength", 0.5),
                    "contradicting_evidence": contradiction_check.get("evidence", ""),
                    "reasoning": contradiction_check.get("reasoning", "")
                })
        
        return contradictions
    
    async def _check_contradiction(self, claim: str, content: str, 
                                 source: Dict[str, Any]) -> Dict[str, Any]:
        """Check if a source contradicts a claim"""
        prompt = f"""Analyze if this source content contradicts the given claim.
        
        Claim: \"{claim}\"        
        Source content: {content[:1500]}...
        
        Return JSON:
        {{
            "contradicts": true/false,
            "strength": 0.0-1.0,
            "evidence": "text that contradicts the claim",
            "reasoning": "explanation of contradiction"
        }}
        
        Only return true if there's clear contradictory evidence."""
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.1)
        
        try:
            # Clean markdown formatting
            cleaned_response = response.strip() if response else ""
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            return json.loads(cleaned_response)
        except:
            return {"contradicts": False, "strength": 0.0, "evidence": "", "reasoning": "Parse error"}
    
    def _calculate_verification_score(self, supporting_sources: List[Dict[str, Any]], 
                                    date_consistency: Dict[str, Any], 
                                    original_confidence: float) -> float:
        """Calculate overall verification score"""
        # Base score from original confidence
        score = original_confidence * 0.3
        
        # Source count bonus
        source_count = len(supporting_sources)
        if source_count >= 2:
            score += 0.3
        elif source_count >= 1:
            score += 0.15
        
        # Source reliability bonus
        if supporting_sources:
            avg_reliability = sum(s.get("reliability", 1) for s in supporting_sources) / len(supporting_sources)
            score += (avg_reliability / 5.0) * 0.2  # Max 0.2 bonus
        
        # Date consistency bonus
        if date_consistency.get("consistent", False):
            score += 0.2
        
        return min(score, 1.0)
    
    def _get_recommendation(self, verified: bool, flagged: bool, 
                          contradictions: List[Dict[str, Any]]) -> str:
        """Get recommendation for claim usage"""
        if contradictions:
            return "MANUAL_REVIEW_REQUIRED - Contradictory evidence found"
        elif verified:
            return "APPROVED - Well-supported claim"
        elif flagged:
            return "REJECT - Insufficient or unreliable evidence"
        else:
            return "CAUTION - Use with additional context"
    
    async def _update_claim_verification(self, verification_results: List[Dict[str, Any]]):
        """Update database with verification results"""
        db = next(get_db())
        
        try:
            for result in verification_results:
                claim_id = result.get("claim_id")
                if claim_id:
                    claim = db.query(Claim).filter(Claim.id == claim_id).first()
                    if claim:
                        claim.confidence = result.get("verification_score", claim.confidence)
                        claim.corroboration_count = result.get("supporting_sources_count", 0)
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            print(f"Error updating claim verification: {e}")
        finally:
            db.close()
    
    def _generate_fact_check_report(self, verification_results: List[Dict[str, Any]]) -> str:
        """Generate human-readable fact-check report"""
        total = len(verification_results)
        if total == 0:
            return "# Fact-Check Report\n\nNo claims were processed."

        verified = len([v for v in verification_results if v["verified"]])
        flagged = len([v for v in verification_results if v["flagged"]])
        contradictions = len([v for v in verification_results if v["contradictions"]])
        
        report = f"""# Fact-Check Report
        
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- Total claims analyzed: {total}
- Verified claims: {verified} ({verified/total*100:.1f}%)
- Flagged claims: {flagged} ({flagged/total*100:.1f}%)
- Claims with contradictions: {contradictions}

## Recommendations
"""
        
        # Add flagged claims
        flagged_claims = [v for v in verification_results if v["flagged"]]
        if flagged_claims:
            report += "\n### Claims Requiring Review\n\n"
            for claim in flagged_claims[:10]:  # Top 10
                report += f"- **{claim['claim']}**\n"
                report += f"  - Sources: {claim['supporting_sources_count']}\n"
                report += f"  - Score: {claim['verification_score']:.2f}\n"
                report += f"  - Recommendation: {claim['recommendation']}\n\n"
        
        return report