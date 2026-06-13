import api from "./api";

/**
 * Fetch semantically similar tickets for a given ticket.
 *
 * @param {number} ticketId - The ticket to find similar ones for
 * @param {number} topK     - How many results to return (1–20)
 * @returns {Promise<{results: SimilarTicket[], method: string}>}
 */
export async function getSimilarTickets(ticketId, topK = 5) {
  const res = await api.get(`/api/tickets/${ticketId}/similar?top_k=${topK}`);
  return res.data;
}
