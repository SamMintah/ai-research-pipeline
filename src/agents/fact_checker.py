from typing import Dict, Any, List, Tuple
import json
from datetime import datetime, timedelta
from src.agents.base import BaseAgent
from src.models import Subject, Claim, Source, ClaimSource
from src.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import and_
import time
import asyncio
from src.llm.base_provider import LLMProvider

class FactCheckerAgent(BaseAgent):
    """Agent for fact-checking and cross-referencing claims"""
    
    def __init__(self, llm_provider: LLMProvider):
        super().__init__(llm_provider)
        self.min_sources_required = 2
        self.confidence_threshold = 0.7
        self.date_tolerance_days = 30
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fact-check all claims for a subject"""
        subject_slug = input_data.get("subject_slug")
        if not subject_slug:
            return {"error": "Subject slug required"}
        
        try:
            # Get all claims for the subject
            claims_data = await self._get_subject_claims(subject_slug)
            if not claims_data or not claims_data.get("claims"):
                self.logger.warning(f"No claims found for subject: {subject_slug}")
                return {"error": "No claims found for subject"}
            
            # Cross-reference claims
            verification_results = await self.batch_check_facts(claims_data["claims"], claims_data["sources"])
            
            # Update database with verification results
            await self._update_claim_verification(verification_results)
            
            # Generate fact-check report
            report = self._generate_fact_check_report(verification_results)
            
            return {
                "subject_slug": subject_slug,
                "total_claims": len(verification_results),
                "verified_claims": len([v for v in verification_results if v.get("verified", False)]),
                "flagged_claims": len([v for v in verification_results if v.get("flagged", False)]),
                "verification_results": verification_results,
                "report": report,
                "checked_at": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"Fact checker process error: {e}", exc_info=True)
            return {
                "error": f"Fact checking failed: {str(e)}",
                "subject_slug": subject_slug,
                "total_claims": 0,
                "verified_claims": 0,
                "flagged_claims": 0,
                "verification_results": [],
                "report": "# Fact-Check Report\n\nFact-checking failed due to processing error.",
                "checked_at": datetime.utcnow().isoformat()
            }

    async def batch_check_facts(self, claims: List[Dict[str, Any]], sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Batch verify multiple claims against available sources using smaller batches to avoid timeouts."""
        
        # Process claims in smaller batches to avoid timeout
        batch_size = 10  # Larger batch size for speed
        all_verification_results = []
        
        for i in range(0, len(claims), batch_size):
            batch_claims = claims[i:i + batch_size]
            print(f"Processing fact-check batch {i//batch_size + 1}/{(len(claims) + batch_size - 1)//batch_size}...")
            
            batched_prompt_parts = []
            for j, claim in enumerate(batch_claims):
                claim_text = claim.get("claim", "")
                claim_date = claim.get("claim_date")
                claim_id = claim.get("id")
                batched_prompt_parts.append(f"Claim {j+1} (ID: {claim_id}):\nClaim Text: \"{claim_text}\"\nClaim Date: {claim_date if claim_date else 'N/A'}\n")
                
            # Limit sources to avoid token limits
            limited_sources = sources[:3]  # Only use top 3 sources per batch
            sources_text = "\n\n".join([f"Source {s.get('id')}: {s.get('title')} ({s.get('url')})\nContent: {s.get('content', '')[:800]}..." for s in limited_sources])
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
    "claim_id": "The UUID of the claim, provided as (ID: ...)",
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
                batch_verification_results = self._parse_json_from_response(batched_response)
                
                if batch_verification_results and isinstance(batch_verification_results, list):
                    all_verification_results.extend(batch_verification_results)
                else:
                    # Fallback for failed batch
                    for claim in batch_claims:
                        all_verification_results.append({
                            "claim_id": claim.get("id"),
                            "claim": claim.get("claim"),
                            "status": "REQUIRES_MORE_INFO",
                            "contradiction_found": False,
                            "reasoning": "Batch processing failed"
                        })
            except Exception as e:
                self.logger.error(f"Error processing batch {i//batch_size + 1}: {e}")
                # Fallback for failed batch
                for claim in batch_claims:
                    all_verification_results.append({
                        "claim_id": claim.get("id"),
                        "claim": claim.get("claim"),
                        "status": "REQUIRES_MORE_INFO",
                        "contradiction_found": False,
                        "reasoning": f"Processing error: {str(e)}"
                    })
        
        initial_verification_results = all_verification_results

        if initial_verification_results is None or not isinstance(initial_verification_results, list):
            self.logger.error("Failed to parse verification results into a list, falling back.")
            fallback_results = []
            for claim in claims:
                fallback_results.append({
                    "claim_id": claim.get("id"),
                    "claim": claim.get("claim"),
                    "verified": False,
                    "flagged": True,
                    "verification_score": 0.1,
                    "supporting_sources_count": 0,
                    "supporting_sources": [],
                    "date_consistency": {"consistent": False, "note": "Fallback due to LLM error"},
                    "contradictions": [],
                    "recommendation": "MANUAL_REVIEW_REQUIRED - LLM processing failed"
                })
            return fallback_results

        final_verification_results = []
        # Use zip to safely combine original claims with LLM results
        for original_claim, llm_result in zip(claims, initial_verification_results):
            # The trusted ID comes from original_claim. The rest comes from the LLM.
            llm_result['claim_id'] = original_claim['id'] 
            
            try:
                verification = await self._verify_claim_detailed(original_claim, sources, llm_result)
                final_verification_results.append(verification)
            except Exception as e:
                self.logger.error(f"Error in detailed verification for claim {original_claim['id']}: {e}", exc_info=True)
                final_verification_results.append({
                    "claim_id": original_claim['id'],
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
        
        return final_verification_results
    
    async def _get_subject_claims(self, subject_slug: str) -> Dict[str, Any]:
        db = next(get_db())
        
        try:
            subject = db.query(Subject).filter(Subject.slug == subject_slug).first()
            if not subject:
                return None
            

            claims = db.query(Claim).filter(Claim.parent_subject_id == subject.id).all()
            sources = db.query(Source).filter(Source.subject_id == subject.id).all()
            
            claims_data = []
            for claim in claims:
                claims_data.append({
                    "id": str(claim.id),
                    "claim": claim.claim,
                    "claim_date": claim.claim_date.isoformat() if claim.claim_date else None,
                    "subject": claim.claim_subject,
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
                "subject": {"name": subject.name, "slug": subject.slug},
                "claims": claims_data,
                "sources": sources_data
            }
            
        finally:
            db.close()  
  
    async def _verify_claim_detailed(self, claim: Dict[str, Any], 
                                  sources: List[Dict[str, Any]], 
                                  initial_llm_result: Dict[str, Any]) -> Dict[str, Any]:
        claim_text = claim.get("claim", "")
        claim_date = claim.get("claim_date")
        
        supporting_sources = await self._find_supporting_sources(claim_text, sources)
        
        date_consistency = await self._check_date_consistency(claim_date, supporting_sources)
        
        verification_score = self._calculate_verification_score(
            supporting_sources, date_consistency, claim.get("confidence", 0)
        )
        
        verified = initial_llm_result.get("status") == "SUPPORTED" and \
                   verification_score >= self.confidence_threshold and \
                   len(supporting_sources) >= self.min_sources_required
        flagged = initial_llm_result.get("status") == "UNSUPPORTED" or \
                  verification_score < 0.5 or \
                  len(supporting_sources) < 1
        
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
    
    async def _find_supporting_sources(self, claim_text: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not sources:
            return []

        sources_parts = []
        for i, source in enumerate(sources):
            content = source.get("content", "")[:1500]
            if not content:
                continue
            sources_parts.append(f"Source {i+1} (ID: {source.get('id')}, Title: {source.get('title', 'Unknown')}, Domain: {source.get('domain', 'Unknown')}):\nContent: {content}\n")

        sources_text = "\n\n".join(sources_parts)

        prompt = f"""Analyze if each source supports the given claim. Be conservative - only say supports if there's clear evidence.
Claim: \"{claim_text}\"\n
Sources:
{sources_text}

For each source, return a JSON object:
{{
    "source_id": "ID",
    "supports": true/false,
    "strength": 0.0-1.0,
    "evidence": "exact quote or snippet",
    "reasoning": "brief explanation"
}}

Return a JSON array of these objects, one per source. Ensure valid JSON."""
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.1)

        support_checks = self._parse_json_from_response(response)
        if support_checks is None:
            return []

        supporting_sources = []
        for check in support_checks:
            if check.get("supports", False):
                source = next((s for s in sources if s.get("id") == check.get("source_id")), None)
                if source:
                    strength = check.get("strength", 0.5)
                    if isinstance(strength, dict):
                        strength = 0.5
                    
                    supporting_sources.append({
                        "source_id": check.get("source_id"),
                        "url": source.get("url"),
                        "domain": source.get("domain"),
                        "title": source.get("title"),
                        "reliability": source.get("reliability", 1),
                        "support_strength": strength,
                        "evidence_snippet": check.get("evidence", "")
                    })

        supporting_sources.sort(key=lambda x: (x.get("reliability", 0) * x.get("support_strength", 0)), reverse=True)
        return supporting_sources
    
    async def _check_date_consistency(self, claim_date: str, supporting_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not claim_date:
            return {"consistent": True, "note": "No date to verify"}

        try:
            claim_datetime = datetime.fromisoformat(claim_date)
        except:
            return {"consistent": False, "note": "Invalid claim date format"}

        if not supporting_sources:
            return {"consistent": False, "note": "No supporting sources"}

        evidence_parts = []
        for i, source in enumerate(supporting_sources):
            evidence = source.get("evidence_snippet", "")[:1000]
            if evidence:
                evidence_parts.append(f"Evidence {i+1} (Source ID: {source.get('source_id')}):\n{evidence}\n")

        evidence_text = "\n\n".join(evidence_parts)

        prompt = f"""Extract all specific dates from each evidence snippet and convert to ISO format (YYYY-MM-DD). Ignore relative terms.
Evidence snippets:
{evidence_text}

Return a JSON object where keys are 'Evidence 1', 'Evidence 2', etc., and values are arrays of ISO dates, e.g.:
{{
    "Evidence 1": ["2023-01-01"],
    "Evidence 2": []
}}
Ensure valid JSON."""

        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.1)

        extracted_dates_dict = self._parse_json_from_response(response)
        if extracted_dates_dict is None:
            return {"consistent": False, "note": "Date extraction failed"}

        date_matches = 0
        date_conflicts = 0

        for dates in extracted_dates_dict.values():
            for date_str in dates:
                try:
                    source_date = datetime.fromisoformat(date_str)
                    days_diff = abs((claim_datetime - source_date).days)
                    if days_diff <= self.date_tolerance_days:
                        date_matches += 1
                    else:
                        date_conflicts += 1
                except:
                    continue

        consistency_score = date_matches / max(date_matches + date_conflicts, 1) if (date_matches + date_conflicts) > 0 else 0
        return {
            "consistent": consistency_score >= 0.7,
            "consistency_score": consistency_score,
            "matches": date_matches,
            "conflicts": date_conflicts
        }
    
    async def _find_contradictions(self, claim_text: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        limited_sources = sources[:10]
        if not limited_sources:
            return []

        sources_parts = []
        for i, source in enumerate(limited_sources):
            content = source.get("content", "")[:1500]
            if not content:
                continue
            sources_parts.append(f"Source {i+1} (ID: {source.get('id')}, Title: {source.get('title', 'Unknown')}):\nContent: {content}\n")

        sources_text = "\n\n".join(sources_parts)

        prompt = f"""Analyze if each source contradicts the claim. Only say contradicts if there's clear evidence.
Claim: \"{claim_text}\"\n
Sources:
{sources_text}

For each source, return a JSON object:
{{
    "source_id": "ID",
    "contradicts": true/false,
    "strength": 0.0-1.0,
    "evidence": "contradicting text",
    "reasoning": "explanation"
}}

Return a JSON array of these objects. Ensure valid JSON."""
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.1)

        contradiction_checks = self._parse_json_from_response(response)
        if contradiction_checks is None:
            return []

        contradictions = []
        for check in contradiction_checks:
            if check.get("contradicts", False):
                source = next((s for s in limited_sources if s.get("id") == check.get("source_id")), {})
                contradictions.append({
                    "source_id": check.get("source_id"),
                    "url": source.get("url"),
                    "title": source.get("title"),
                    "contradiction_strength": check.get("strength", 0.5),
                    "contradicting_evidence": check.get("evidence", ""),
                    "reasoning": check.get("reasoning", "")
                })

        return contradictions
    
    def _calculate_verification_score(self, supporting_sources: List[Dict[str, Any]], 
                                    date_consistency: Dict[str, Any], 
                                    original_confidence: float) -> float:
        score = original_confidence * 0.3
        
        source_count = len(supporting_sources)
        if source_count >= 2:
            score += 0.3
        elif source_count >= 1:
            score += 0.15
        
        if supporting_sources:
            avg_reliability = sum(s.get("reliability", 1) for s in supporting_sources) / len(supporting_sources)
            score += (avg_reliability / 5.0) * 0.2
        
        if date_consistency.get("consistent", False):
            score += 0.2
        
        return min(score, 1.0)
    
    def _get_recommendation(self, verified: bool, flagged: bool, 
                          contradictions: List[Dict[str, Any]]) -> str:
        if contradictions:
            return "MANUAL_REVIEW_REQUIRED - Contradictory evidence found"
        elif verified:
            return "APPROVED - Well-supported claim"
        elif flagged:
            return "REJECT - Insufficient or unreliable evidence"
        else:
            return "CAUTION - Use with additional context"
    
    async def _update_claim_verification(self, verification_results: List[Dict[str, Any]]):
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
            self.logger.error(f"Error updating claim verification: {e}", exc_info=True)
        finally:
            db.close()
    
    def _generate_fact_check_report(self, verification_results: List[Dict[str, Any]]) -> str:
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
        
        flagged_claims = [v for v in verification_results if v["flagged"]]
        if flagged_claims:
            report += "\n### Claims Requiring Review\n\n"
            for claim in flagged_claims[:10]:
                report += f"- **{claim['claim']}**\n"
                report += f"  - Sources: {claim['supporting_sources_count']}\n"
                report += f"  - Score: {claim['verification_score']:.2f}\n"
                report += f"  - Recommendation: {claim['recommendation']}\n\n"
        
        return report
