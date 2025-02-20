<h1 align="center">
    <b>The Vision of Autonomic Computing:</b>
    <b>Can We Make it a Reality?</b>
</h1>

This repository collects all our ongoing work towards achieving the Vision of Autonomic Computing (ACV).

## News
* [2025/01/31] We released a [paper](https://arxiv.org/abs/2501.19056) that further explores the development of self-learning agents for microservice management.
* [2024/12/17] Checkout the initial release of [AutoKube](self_managing_systems/microservice/AutoKube/README.md). It aims to be a general tool to simplify the management of microservices in Kubernetes by leveraging a LLM-powered agent management system. The tool is built upon the related research work.
* [2024/12/17] We release the [code artifact](self_managing_systems/microservice/paper_artifact_arXiv_2407_14402/README.md) for the initial research exploration on applying [LLM-based agents for microservice self-management](https://aka.ms/ACV-LLM). 

## What is ACV?

The Vision of Autonomic Computing is a vision of self-managing systems that can adapt to their environment and requirements. The vision, proposed in the early 2000s, emerged as a response to the growing complexity of managing computing systems. It has since become a long-standing goal in the field of computer science, highlighting the need for systems capable of self-management. The initial vision is based on four key properties: self-configuration, self-optimization, self-healing, and self-protection. These properties are designed to enable systems to manage themselves with minimal human intervention. For example, in cloud computing, a system utilizing these properties could automatically detect and recover from server failures, optimize resource allocation based on current demand, and defend against potential security threats without requiring manual oversight. More details can be found in the [ACV paper](https://ieeexplore.ieee.org/document/1160055) and the wikipedia page on [Autonomic Computing](https://en.wikipedia.org/wiki/Autonomic_computing).

## Potential of Realizing ACV via LLMs

 Despite significant efforts and progress over the past two decades, the realization of ACV is still elusive due to numerous grand challenges outlined in the ACV paper, many of which hinge on breakthroughs in AI. Recent advances in AI, particularly Large Language Models (LLMs), offer a unique opportunity to build upon and advance this vision. With their extensive knowledge, contextual understanding, and adaptive decision-making capabilities, LLMs appear well-suited to address longstanding challenges in autonomic computing. For instance, LLMs could be used to dynamically generate configurations for complex systems or provide real-time diagnostics and troubleshooting for large-scale cloud infrastructures.

## Workstreams
To drive the ACV vision forward, we are currently working on two major workstreams that address both traditional and emerging domains for applying autonomic computing. 
* [**Self-Managing Systems**](self_managing_systems/README.md): This workstream focuses on developing general self-managing systems, particularly within the traditional autonomic computing domain, such as achieving ACV for large-scale distributed system management. More details about the ongoing work can be found in the [self-managing systems](self_managing_systems/README.md) folder.
* [**Autonomic Personal Computing**](autonomic_personal_computing/README.md): This workstream explores applying ACV principles to the emerging field of intelligent personal assistants. The goal is to enable autonomous engagement with users by understanding them and delivering tailored assistance. More details about the ongoing work can be found in the [autonomic personal computing](autonomic_personal_computing/README.md) folder.

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
