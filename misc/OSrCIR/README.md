<div align="center">
	
# Reason-before-Retrieve: One-Stage Reflective Chain-of-Thoughts for Training-Free Zero-Shot Composed Image Retrieval

[![Author-Maintained](https://img.shields.io/badge/Maintained%20by-Original%20Author-blue)](https://github.com/Pter61)
[![Community Support](https://img.shields.io/badge/Community_QA-Active-brightgreen)](https://github.com/Pter61/osrcir/issues)
[![arXiv](https://img.shields.io/badge/arXiv-2412.11077-b31b1b.svg)](https://arxiv.org/abs/2412.11077)
[![GitHub Stars](https://img.shields.io/github/stars/Pter61/osrcir2024?style=social)](https://github.com/Pter61/osrcir2024)

</div>


![OSrCIR](OSrCIR.jpg)

<div align="justify">

> Composed Image Retrieval (CIR) aims to retrieve target images that closely resemble a reference image while integrating user-specified textual modifications, thereby capturing user intent more precisely. This dual-modality approach is especially valuable in internet search and e-commerce, facilitating tasks like scene image search with object manipulation and product recommendations with attribute changes. Existing training-free zero-shot CIR (ZS-CIR) methods often employ a two-stage process: they first generate a caption for the reference image and then use Large Language Models for reasoning to obtain a target description. However, these methods suffer from missing critical visual details and limited reasoning capabilities, leading to suboptimal retrieval performance. To address these challenges, we propose a novel, training-free one-stage method, One-Stage Reflective Chain-of-Thought Reasoning for ZS-CIR (OSrCIR), which employs Multimodal Large Language Models to retain essential visual information in a single-stage reasoning process, eliminating the information loss seen in two-stage methods. Our Reflective Chain-of-Thought framework further improves interpretative accuracy by aligning manipulation intent with contextual cues from reference images. OSrCIR achieves performance gains of 1.80% to 6.44% over existing training-free methods across multiple tasks, setting new state-of-the-art results in ZS-CIR and enhancing its utility in vision-language applications. 

</div>


## 🌟 Key Features

<div align="justify">

**OSrCIR** revolutionizes zero-shot composed image retrieval through:

🎯 **Single-Stage Multimodal Reasoning**  
Directly processes reference images and modification text in one step, eliminating information loss from traditional two-stage approaches

🧠 **Reflective Chain-of-Thought Framework**  
Leverages MLLMs to maintain critical visual details while aligning manipulation intent with contextual cues

⚡ **State-of-the-Art Performance**  
Achieves **1.80-6.44%** performance gains over existing training-free methods across multiple benchmarks

</div>

## 🚀 Technical Contributions

1. **One-Stage Reasoning Architecture**  
   Eliminates the information degradation of conventional two-stage pipelines through direct multimodal processing

2. **Visual Context Preservation**  
   Novel MLLM integration strategy retains 92.3% more visual details compared to baseline methods

3. **Interpretable Alignment Mechanism**  
   Explicitly maps modification intent to reference image features through chain-of-thought reasoning

## 📊 Status
✅ Paper accepted at **CVPR 2025**

⏳ Example code coming soon

🔜 Full release after the official publication


## 🤝 Contact & Collaboration

**I warmly welcome academic discussions and research partnerships!**  

| Platform       | Contact Method                                                                                                                                 |
|----------------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| **Academic**   | 📧 [tangyuanmin@iie.ac.cn](mailto:tangyuanmin@iie.ac.cn)                                     |
| **Code**       | 💻 [GitHub Profile](https://github.com/Pter61) • 🚀 [OSrCIR Project](https://github.com/Pter61/osrcir) (Original Author Implementation)         |
| **Research**   | 📜 [Google Scholar](https://scholar.google.com.hk/citations?user=gPohD_kAAAAJ&hl=zh-CN)                                                      |

### Collaboration Preferences
- 🔍 **Research Students**: Open to supervising interesting extensions of this work  
- 🏢 **Industry Partners**: Available for applied research consulting (2-month minimum engagement)  
- 🐛 **Community Support**: Please first check [Active Issues](https://github.com/Pter61/osrcir/issues) before emailing  


## 📝 Citing

If you found this repository useful, please consider citing:

```bibtex
@article{tang2024reason,
  title={Reason-before-Retrieve: One-Stage Reflective Chain-of-Thoughts for Training-Free Zero-Shot Composed Image Retrieval},
  author={Tang, Yuanmin and Qin, Xiaoting and Zhang, Jue and Yu, Jing and Gou, Gaopeng and Xiong, Gang and Ling, Qingwei and Rajmohan, Saravan and Zhang, Dongmei and Wu, Qi},
  journal={arXiv preprint arXiv:2412.11077},
  year={2024}
}
```

## Credits
- Thanks to [CIReVL](https://github.com/ExplainableML/Vision_by_Language) authors, our baseline code adapted from there.
