# Related work

What mm-arena builds on, and how it differs. Every entry below was checked against its primary
page (arXiv record, publisher, RePEc or repository) in October 2026.

## Position

LLM trading benchmarks score realized P&L on historical or live market data. That mixes
forecasting, execution and luck, and the optimal policy is unknown. mm-arena isolates two
skills a market maker needs, belief updating and pricing adverse selection, in games where the
optimal quote is computable. Each component exists elsewhere. The combination is new: an open
LLM benchmark with exact per-quote references, luck-adjusted P&L under common random numbers,
and perturbed variants that test recall.

## Market microstructure

- Glosten, L. R. and Milgrom, P. R. (1985). Bid, ask and transaction prices in a specialist
  market with heterogeneously informed traders. *Journal of Financial Economics* 14(1), 71-100.
  The model the simulator implements: sequential unit trades, a fraction of informed traders,
  zero-profit quotes `a = E[V | buy]`, `b = E[V | sell]`. Source of the `glosten-milgrom`
  reference.
- Kyle, A. S. (1985). Continuous auctions and insider trading. *Econometrica* 53(6), 1315-1336.
  The other canonical informed-vs-noise model (batch auction, not quote-driven).
- Copeland, T. E. and Galai, D. (1983). Information effects on the bid-ask spread. *Journal of
  Finance* 38(5), 1457-1469. The spread as an option written to informed traders.
- Ho, T. and Stoll, H. R. (1981). Optimal dealer pricing under transactions and return
  uncertainty. *Journal of Financial Economics* 9(1), 47-73. Inventory-driven quoting.
- Avellaneda, M. and Stoikov, S. (2008). High-frequency trading in a limit order book.
  *Quantitative Finance* 8(3), 217-224. Inventory-aware quoting with elastic order flow.
- Das, S. (2005). A learning market-maker in the Glosten-Milgrom model. *Quantitative Finance*
  5(2), 169-180. A market maker that tracks a posterior over the value from order flow; the
  `bayes` reference does the same exactly.
- Das, S. and Magdon-Ismail, M. (2008). Adapting to a market shock: optimal sequential
  market-making. *NIPS 21*, 361-368. Shows the myopic Bayesian quote is not optimal over the
  whole game, which is why mm-arena calls its reference "myopic" and allows scores above 100.

## Variance reduction in agent evaluation

- Zinkevich, M., Bowling, M., Bard, N., Kan, M. and Billings, D. (2006). Optimal unbiased
  estimators for evaluating agent performance. *AAAI-06*, 573-578.
- Billings, D. and Kan, M. (2006). A tool for the direct assessment of poker decisions (DIVAT).
  *ICGA Journal* 29(3), 119-142.
- Burch, N., Schmid, M., Moravcik, M., Morrill, D. and Bowling, M. (2018). AIVAT: a new variance
  reduction technique for agent evaluation in imperfect information games. *AAAI-18*.
  arXiv:1612.06915. The template for xPnL: replace realized outcomes of chance events with their
  exact expectation, keep every consequence of the agent's choices.
- Li, B., Chen, Y. and Huang, L. (2026). AV-AIVAT: 74x cheaper agent evaluation with certified
  anytime-valid stopping in imperfect-information games. arXiv:2608.06362. AIVAT applied to LLM
  agents in poker.
- Klein, D. J., Abeysuriya, R. G., Stuart, R. M. and Kerr, C. C. (2024). Noise-free comparison
  of stochastic agent-based simulations using common random numbers. arXiv:2409.02086.
- Miller, E. (2024). Adding error bars to evals: a statistical approach to language model
  evaluations. arXiv:2411.00640. Clustered standard errors and paired comparisons for LLM evals.

## LLMs in markets

- Optiver (2026-04-27). Where AI trading models work (and where they still fall short).
  Optiver technology blog. The closest precedent: unnamed LLMs on internal market-making games,
  reported qualitatively as failing to update on new information. No released code or metrics.
- Lopez-Lira, A. (2025). Can large language models trade? Testing financial theories with LLM
  agents in market simulations. arXiv:2504.10789. LLM agents in a simulated market; market
  making appears only as a prompted persona.
- Chen, Y. et al. (2025). StockBench: can LLM agents trade stocks profitably in real-world
  markets? arXiv:2510.02209.
- Li, H. et al. (2025). InvestorBench: a benchmark for financial decision-making tasks with
  LLM-based agent. *ACL 2025*. arXiv:2412.18174.
- Xie, Q. et al. (2024). FinBen: a holistic financial benchmark for large language models.
  *NeurIPS 2024 Datasets and Benchmarks*. arXiv:2402.12659.
- Qian, L. et al. (2025). When agents trade: live multi-market trading benchmark for LLM agents
  (Agent Market Arena). arXiv:2510.11695.
- Yu, H., Li, F. and You, J. (2025). LiveTradeBench: seeking real-world alpha with large
  language models. arXiv:2511.03628.
- nof1 (2025). Alpha Arena, Season 1. Six LLMs trading crypto perpetuals with real money for two
  weeks, one account each, ranked on realized P&L.
- Henning, T., Ojha, S. M., Spoon, R., Han, J. and Camerer, C. F. (2025). LLM agents do not
  replicate human market traders: evidence from experimental finance. arXiv:2502.15800.

## Market simulators and RL market making

- Byrd, D., Hybinette, M. and Balch, T. H. (2019). ABIDES: towards high-fidelity market
  simulation for AI research. arXiv:1904.12066.
- Jerome, J., Sanchez-Betancourt, L., Savani, R. and Herdegen, M. (2023). Mbt-gym: reinforcement
  learning for model-based limit order book trading. *ICAIF '23*. arXiv:2209.07823.
- Frey, S. et al. (2023). JAX-LOB: a GPU-accelerated limit order book simulator. arXiv:2308.13289.
- Spooner, T., Fearnley, J., Savani, R. and Koukorinis, A. (2018). Market making via
  reinforcement learning. *AAMAS 2018*. arXiv:1804.04216.

## Probabilistic reasoning and memorization

- Samanta, A. et al. (2026). BayesBench: evaluating LLM belief trajectories under multi-turn
  evidence accumulation. arXiv:2606.30850.
- Imran, S. et al. (2025). Are LLM belief updates consistent with Bayes' theorem? ICML 2025
  Workshop on Assessing World Models. arXiv:2507.17951.
- Mirzadeh, I. et al. (2024). GSM-Symbolic: understanding the limitations of mathematical
  reasoning in large language models. *ICLR 2025*. arXiv:2410.05229. The precedent for
  perturbed variants of known problems as a recall probe.
- Duan, J. et al. (2024). GTBench: uncovering the strategic reasoning limitations of LLMs via
  game-theoretic evaluations. arXiv:2402.12348.

## Practice tools for humans

Several open-source tools implement interview market-making games for human practice, some with
informed and noise counterparties and a Bayesian dealer (for example Quantdle and Picked Off on
GitHub). None evaluates LLMs or reports luck-adjusted scores.
