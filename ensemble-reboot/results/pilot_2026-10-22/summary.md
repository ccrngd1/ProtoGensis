# Summary: pilot_2026-10-22

1139 records. All numbers trace to record_ids (inline or in record_groups.json).

## Spend

- **Billed spend: $75.4628** over 1049 API calls (query: `sum(cost_usd) where billed` — vote events excluded).
- Attributed vote-event cost: $12.4328 over 90 programmatic-vote records (sum of each vote's parent proposal calls; NOT billed — the parents are already in the billed total).

Latency exclusions (config/latency_exclusions.yaml; excluded from p50/p95 latency only, kept in accuracy/cost):
- `5047626ad9554cd4`: Harness process was SIGSTOPped for ~4-6 minutes at 2026-10-23T01:32Z while this call was in flight; wall-clock latency includes the stop and does not reflect API latency.
- `de26961352b24f30`: Harness process was SIGSTOPped for ~4-6 minutes at 2026-10-23T01:32Z while this call was in flight; wall-clock latency includes the stop and does not reflect API latency.
- `2aaa7145744e462c`: Harness process was SIGSTOPped for ~4-6 minutes at 2026-10-23T01:32Z while this call was in flight; wall-clock latency includes the stop and does not reflect API latency.

## Accuracy / cost / latency

Cost marked `attr.` is attributed (sum of the row's parent proposal calls, labeled on programmatic-vote rows); it is already contained in the billed total and must not be added on top of it.

| arm | model | effort | set | acc (95% CI) | n | trunc | cost$ | $/correct | p50/p95 lat (s) | records |
|---|---|---|---|---|---|---|---|---|---|---|
| a1 | amazon.nova-2-lite-v1:0 | medium | code | 0.30 [0.11,0.60] | 10 | 0 | 0.292 | 0.0975 | 51.411/103.662 | 5e0976a9d64b4330,09cb55ab22444b84,9b4ab8776aa64096,64c727ff089648cc,37caa5738e624d75,e088485a60eb48f6,c715d516aada4616,8846b502744741ba,639be11d696a4193,0687ecc82c68499b |
| a1 | amazon.nova-2-lite-v1:0 | medium | gpqa | 0.50 [0.24,0.76] | 10 | 1 | 0.431 | 0.0862 | 85.343/181.792 | 25b38e7dcf1843b9,ac40fd1db1044b86,b8c41ea50f4a49f6,5c13f6963cad4e20,d2d9dab7387b4637,c4fbf477fa714a62,6484801b3c44417c,82a4549bb8aa4fd8,aeecf26951044e9e,c710f279869b474f |
| a1 | amazon.nova-2-lite-v1:0 | medium | math | 0.70 [0.40,0.89] | 10 | 2 | 0.349 | 0.0499 | 51.764/196.545 | e23958f865e5404d,2decbf50c9c74e57,41d1d9e383c04390,042a3b935d4b4c91,2398adb6885a4a44,df313b3c617448ec,b6f558a96ffc43b0,1828b52ddbda4e7f,1bdabc58894b4c66,9925087a722c48d9 |
| a1 | anthropic.claude-fable-5-1 | high | code | 0.90 [0.60,0.98] | 10 | 0 | 1.013 | 0.1126 | 18.294/82.593 | 1ce0b5dbdd6146ab,8e1d7e3a0cc24852,efe8233cde6243ce,8eb652b4462d4d9c,5c6d27ea6fbc4ef7,9b7874a0ee494db5,7b83d31780d54272,1eaa27f7502346a5,f4da7ccc84204ac7,0770906a3505486c |
| a1 | anthropic.claude-fable-5-1 | high | gpqa | 0.80 [0.49,0.94] | 10 | 0 | 0.364 | 0.0455 | 6.598/36.772 | 4e1627b590ec4224,05eca41fecd745c9,3a3d164c3bba41e4,d71c3aaf83e0469a,91a231b42397474c,de8e5963d878482f,4f276e55bcb147ac,da19febaed75438b,2a7db7ad6b174065,bdd8101119a14b50 |
| a1 | anthropic.claude-fable-5-1 | high | math | 1.00 [0.72,1.00] | 10 | 0 | 2.506 | 0.2506 | 23.689/310.556 | e8256f33243e4a1f,81f9670465354c08,57e0a271e2b14f38,ae9eafc658434e70,93f107c681d44763,cfc2f66b0b554eb6,40294a4acd264162,5a489013ad4e4f59,89609aa6ca454c56,a2d6ef8275314dbc |
| a1 | anthropic.claude-haiku-5-5 | medium | code | 0.80 [0.49,0.94] | 10 | 0 | 0.025 | 0.0032 | 13.043/100.775 | e46e5bab04ea4e30,da8aca8b987b4ace,d4f19160986846e2,ecd775b798cc4ba1,e3302dd79ac04d91,fc4a00af5044480f,d75ab07456024258,b8c287c5264146e6,e006e61277f34a56,a9b36d2bea8d47e2 |
| a1 | anthropic.claude-haiku-5-5 | medium | gpqa | 0.60 [0.31,0.83] | 10 | 0 | 0.010 | 0.0016 | 6.17/15.93 | 8ba19fcd26a64665,9a7010eb843947d7,0a238fc4356147d8,4c17ca77ae0a411c,555cb838efc1400c,716201ef991246d6,05f5dbafd671475d,356a31045b914667,53819dcb5e3a42eb,ac6a9cb4836f4137 |
| a1 | anthropic.claude-haiku-5-5 | medium | math | 0.80 [0.49,0.94] | 10 | 0 | 0.037 | 0.0046 | 16.416/114.893 | 365980ad9bf24051,43f47c5340fe41cd,26ad36bb1cdf4fc0,a3ff5c75f8694ab8,0c8c3403f5504e68,9fa8326f05a24d65,6b5d173826b344db,7a006b1270704e0a,a3060fc2bebc405c,cb782e7d4e9b4a68 |
| a1 | anthropic.claude-opus-5-5 | medium | code | 0.90 [0.60,0.98] | 10 | 0 | 0.333 | 0.037 | 15.66/25.301 | 364b1edb21ba4e37,d8b41f82b22948d7,ed277fe9f9d8442b,72bcb7014b034c32,c373e6ac6c564ce1,558830ddbfad42d0,2de3fc0feaf54d73,0fa2744553124229,8e86c05dea2942a4,62f50346406e4047 |
| a1 | anthropic.claude-opus-5-5 | medium | gpqa | 0.90 [0.60,0.98] | 10 | 0 | 0.179 | 0.0199 | 7.728/15.859 | 90f6b894497a4419,044c8a581a154060,b7ba53704ce840e6,f43ff932217a4abe,227827d6f20f4211,37852613a0e24e50,eb000a1ee11f4508,c35c815fb8554d64,cc4781f70f3d4d7b,38c703d209f343f0 |
| a1 | anthropic.claude-opus-5-5 | medium | math | 1.00 [0.72,1.00] | 10 | 0 | 0.508 | 0.0508 | 13.271/78.272 | 0f7532b4661a49d1,64fb4f20a1064245,8cbca02792d94b72,4d76aa340bcf4e88,424bf11919b34f42,c314b86f57704140,5953f5ac9f4f4ddc,950e4d35c5c646f5,49ec6ee84c214f4d,f62774b2dd264749 |
| a1 | anthropic.claude-sonnet-5-5 | medium | code | 0.80 [0.49,0.94] | 10 | 0 | 0.127 | 0.0159 | 8.462/15.156 | c7f081b8b2e5455c,a7ad81c030314344,c93c570eee4e427e,2ea3e06f6fbd4692,d5190147a6404957,4757fe85c96146fa,2687ffb1dc2b48bd,76e918cdf14749e2,2551c62e19884d75,05b94ddaec774034 |
| a1 | anthropic.claude-sonnet-5-5 | medium | gpqa | 0.80 [0.49,0.94] | 10 | 0 | 0.069 | 0.0087 | 5.004/9.685 | d450a5f8bc3d4a85,e13b91ec8a66425c,2c547c8713ce40bd,6bb0a81eff084125,adf71e884d014d73,b37e83f8ab3246f1,5a0ef5572dee4587,1507111b82844c1c,9c792a4c0fb347fe,942ae6386c0043f2 |
| a1 | anthropic.claude-sonnet-5-5 | medium | math | 0.90 [0.60,0.98] | 10 | 0 | 0.221 | 0.0246 | 9.908/49.695 | 57a1bcccbff64ba2,b9053269f2fe453d,ec867662a77d4ade,f98f85f4b6924655,262a562c51ba467f,b077f3f3996c476a,c8ee7e556e48480d,0c1ddc4ac6df487e,dafa8277c46c4718,023036377c8746dc |
| a1 | moonshotai.kimi-k3 | max | code | 0.80 [0.49,0.94] | 10 | 0 | 2.002 | 0.2502 | 161.259/661.527 | beb562dfe5564b85,a54162bc550944f6,de309df8e7e047d7,6f91efd8adef41f6,98a43800bc134fa6,5de03c668317423d,030558c0a2884c01,5a85e8ab01e241e8,89a2d511997e4696,b146627200274b2f |
| a1 | moonshotai.kimi-k3 | max | gpqa | 0.90 [0.60,0.98] | 10 | 0 | 0.773 | 0.0859 | 20.402/668.602 | 200b0cb6899b4e61,9136dc2a1f5c421e,07eb17a07ba4474f,cbb50953fc364123,cdb0ef34c02b4374,0f7480dd79db442d,1ca5b13f5c6648ef,77724eac4acd45c1,2c2fe859573d4cdc,17a9fd2347194c95 |
| a1 | moonshotai.kimi-k3 | max | math | 1.00 [0.72,1.00] | 10 | 0 | 1.711 | 0.1711 | 104.229/676.096 | 63e40072c90244ec,2d710b96d2cd42b8,b9adcf1575df417e,3c978ed5ad564e54,16c271ff5b464787,713b02a761654c01,1151111031e24654,796d0df7708b4397,78bd549125ac4b72,f4290be4ef5a426f |
| a1 | openai.gpt-6-astra | medium | code | 0.90 [0.60,0.98] | 10 | 0 | 0.447 | 0.0496 | 12.865/30.909 | 68f6fce3e9f64f0f,1e1cb6bd3cb74dbe,ee2cc4b807354799,c6984989923c43e5,28266176050246e6,9a05aa3ea31c4a21,3ca42c658e6e4642,2a248d35d7484523,7477a9fdbb3d493e,c1a1f06931504809 |
| a1 | openai.gpt-6-astra | medium | gpqa | 0.90 [0.60,0.98] | 10 | 0 | 0.212 | 0.0235 | 4.133/29.146 | 9a1dcd833dfa45c9,a184efc9b3c443d5,766d65acfb764bc1,192dfef3b8a24cae,8425fcdfd15c4b4d,3f69be36a7254857,c9f5aa850de04dc0,8b90d69155f04fee,71b64a60e74345bc,0b91744e33514414 |
| a1 | openai.gpt-6-astra | medium | math | 1.00 [0.72,1.00] | 10 | 0 | 0.658 | 0.0658 | 15.084/60.907 | d15d84c274b649b8,acce5056e7c040c2,ae48358b09e24099,c2023ab2c622460a,fd3995e29ea34375,528574d864094f67,cd93c4b721e7438f,d9ad03ef15f14f7a,a2f38f50e7804ffd,2def4437b81d4beb |
| a1 | openai.gpt-6-luna | medium | code | 0.80 [0.49,0.94] | 10 | 0 | 0.016 | 0.002 | 18.024/66.588 | 093f1cb0d7244702,46f244576f794041,6593f50773624ba2,621a3426a8804d6a,c3fc25c20a164d3c,4bd587e665d44e49,92254f1668dc423b,4a69b756b279417e,929aac536b1144d4,d67018141a994775 |
| a1 | openai.gpt-6-luna | medium | gpqa | 0.70 [0.40,0.89] | 10 | 0 | 0.009 | 0.0013 | 14.169/43.051 | f9cae34a65a64cb0,5613f07913c94622,2aebfff3326d4e30,8c3d44b920bf4293,58f5bcb28dd0403c,f4ea62fd571e449d,7d4d1802ae324310,43aba69f8ed14cc6,b08ed305c3d94db7,9445d0dea8b84ad1 |
| a1 | openai.gpt-6-luna | medium | math | 1.00 [0.72,1.00] | 10 | 0 | 0.025 | 0.0025 | 24.515/159.552 | 0bc04b0020e740c3,e060054390dd4388,73095a60483a4ed4,536b5dfcd9754611,64aad124242d44d1,691f6154a78f4141,b0818584a11342c4,5145cff0630d40e2,49c10c4b8935448d,8ed8c9bf854743fb |
| a1 | openai.gpt-6.1-sol | medium | code | 0.90 [0.60,0.98] | 10 | 0 | 0.091 | 0.0101 | 11.94/39.098 | 7ccfb503dc6b43cb,4a529a24e80f4b72,3e091124a04b4f7d,6e3845eb21c24d85,f85638f641a04391,83d5ef0596ff48c1,d593b385614c4b2a,8fc3ed6935804f90,81188fc22b0541a1,a309c1aca5b7432c |
| a1 | openai.gpt-6.1-sol | medium | gpqa | 0.80 [0.49,0.94] | 10 | 0 | 0.039 | 0.0049 | 5.508/25.996 | 5b1108067c1b49f0,70bedfad6f8d4f53,2320c00e3880481f,a46b358a3801400e,9095aa61bff44f39,87e087ac1e664d92,0c2035e7825d409d,4b4f8a715d6f45df,bb9fd6da713349b7,d5b1dc8df777421d |
| a1 | openai.gpt-6.1-sol | medium | math | 1.00 [0.72,1.00] | 10 | 0 | 0.140 | 0.014 | 18.401/61.255 | 4a40280fe10d4386,3a5370d0aadf4dd4,fcdbeba50d554215,a37a337da6b34c37,f3b82e5e89df492a,425e920bbe9a470b,611f0f88f24b4fc3,79cda49676d74cfb,4c9db0d83aee493d,f0a73d73840840df |
| a1 | xai.grok-4.7 | high | code | 0.60 [0.31,0.83] | 10 | 3 | 1.223 | 0.2039 | 415.812/844.18 | 1e78f4f2f3964b3a,b5c03b0984e54e78,a0c93884dff14ae2,d3f903c16b76499d,c5853c2b5bca439e,8173c42308544812,e7e78276cbe64c5a,3c9a9b7bbf8e47e3,4851ac80b31243aa,6868b86addc34c69 |
| a1 | xai.grok-4.7 | high | gpqa | 0.70 [0.40,0.89] | 10 | 2 | 0.855 | 0.1222 | 204.785/827.998 | 420421a011e8497c,55af4b7ec32444bc,22bb79cf3da1403b,cbf31984259a4132,89b005e614954522,41eb570216c4466a,042bd3c11c2e45ca,68d3d6f6c4ca4f90,52cac66bc8d04706,e7347f76480f4a06 |
| a1 | xai.grok-4.7 | high | math | 0.50 [0.24,0.76] | 10 | 5 | 1.418 | 0.2835 | 407.261/849.05 | 6ee5749d9f7445f6,a4d4e4f2f38e4333,7f11cb33621441ff,2bd0fff6ce9e4e65,0574be5a6971485e,fc8e19e6db7a4059,413cbc2f974448b7,7ab8300a576f4fd1,20bc6d354c224536,c2784910da024324 |
| a2 | anthropic.claude-opus-5-5 | medium | gpqa | 0.88 [0.74,0.95] | 40 | 0 | 0.760 | 0.0217 | 8.763/16.697 | see record_groups.json#a2_global.anthropic.claude-opus-5-5_medium_gpqa (n=40) |
| a2 | openai.gpt-6-luna | medium | math | 0.90 [0.77,0.96] | 40 | 0 | 0.123 | 0.0034 | 26.688/210.417 | see record_groups.json#a2_global.openai.gpt-6-luna_medium_math (n=40) |
| a2 | openai.gpt-6.1-sol | medium | code | 0.90 [0.77,0.96] | 40 | 0 | 0.382 | 0.0106 | 14.974/43.947 | see record_groups.json#a2_global.openai.gpt-6.1-sol_medium_code (n=40) |
| a2 | programmatic-vote | medium | code | 0.90 [0.60,0.98] | 10 | 0 | 0.472 attr. | 0.0525 | - | 421656c298154c98,5462d71808ec42f2,1695685c6f874e8f,fe4d8e17d1a04e5b,1262cea581aa4537,fecd24d8bc0141dc,7f4dccd6cd414da3,b8b80dc2823449f8,da3af676c1214b5f,be701791f0444db9 |
| a2 | programmatic-vote | medium | gpqa | 0.90 [0.60,0.98] | 10 | 0 | 0.939 attr. | 0.1044 | - | 614ee6ab06124092,a7ec5d53a517449c,c4bc2a3e42c245ce,facd9384654a44a5,d1c856a4f7a04bf0,a5955c95d2b4401c,e9a85a5be81c48aa,1b2d346122584a53,6a7922168aa64a94,43edb17561a84920 |
| a2 | programmatic-vote | medium | math | 1.00 [0.72,1.00] | 10 | 0 | 0.149 attr. | 0.0149 | - | ff6396836b3849b6,4587d174c7614db8,8a003c4443044364,3b50c2fc53ca4f12,d433b1f2dbfc43d3,eaaae53cb09a40a8,2bcf66f99df14bce,d06802daa1444aaa,61bfb272ba6d42fa,4e7458eb6f414f5d |
| a3 | anthropic.claude-opus-5-5 | medium | gpqa | 0.86 [0.76,0.92] | 70 | 0 | 1.689 | 0.0282 | 10.497/20.167 | see record_groups.json#a3_global.anthropic.claude-opus-5-5_medium_gpqa (n=70) |
| a3 | openai.gpt-6-luna | medium | math | 0.94 [0.86,0.98] | 70 | 0 | 0.190 | 0.0029 | 22.588/152.399 | see record_groups.json#a3_global.openai.gpt-6-luna_medium_math (n=70) |
| a3 | openai.gpt-6.1-sol | medium | code | 0.90 [0.81,0.95] | 70 | 0 | 0.742 | 0.0118 | 14.927/55.368 | see record_groups.json#a3_global.openai.gpt-6.1-sol_medium_code (n=70) |
| a3 | programmatic-vote | medium | code | 0.90 [0.60,0.98] | 10 | 0 | 0.742 attr. | 0.0825 | - | 7534b549ebdf4629,3b77417d9ad4468a,4663c034df314e6e,403a606b75514477,133332ea75e44c7e,f18a0d3521614e0a,ae5b524497d54421,246515e747b5454b,eb9b161067de4e3f,dd46e9bb3e7c4fb0 |
| a3 | programmatic-vote | medium | gpqa | 0.90 [0.60,0.98] | 10 | 0 | 1.689 attr. | 0.1877 | - | 83eb6cfe7c454dcd,2c1727ed10894481,62bf5722c7e34fc3,c39f49cd1ebe4d9d,4343a2e18e2e4a8c,7ea67012f2f94e28,34a0a5498dc5446e,78a6a27673ec4bbb,fa8709dfa4e44549,7ead7860633646a1 |
| a3 | programmatic-vote | medium | math | 1.00 [0.72,1.00] | 10 | 0 | 0.190 attr. | 0.019 | - | e90df938483b4d67,56fb65a0e4034ab1,bcdbd082ad004331,a28e28af9bfa4fa5,499de412b1b447db,08e14d3eed4f4d40,3c7aec29aa134c71,f049ae479a754b93,b2e973961c004281,39f526ab54e64f81 |
| a4-vote | programmatic-vote | default | code | 0.90 [0.60,0.98] | 10 | 0 | 3.316 attr. | 0.3684 | - | b255f36acb9b468a,b8f783687483480c,a2c25dce14e1484f,688407da21cd4e31,f6392c3582e0409a,46e19512a7474e4e,655ebd0759714416,a08e6535271041f9,05f7e18cb9cb47ae,ffd972d275f945c4 |
| a4-vote | programmatic-vote | default | gpqa | 0.80 [0.49,0.94] | 10 | 0 | 1.667 attr. | 0.2084 | - | 4bc096e0dd53430d,1febcce97c41496f,fc6d9427c3804ed5,49f85c04f09647ef,80311a6858f544f2,d6156aad2f09460d,4eb75f9442234e1b,e1287403e3fc4455,acaeaea1414f45a3,fc55011b992e4352 |
| a4-vote | programmatic-vote | default | math | 1.00 [0.72,1.00] | 10 | 0 | 3.269 attr. | 0.3269 | - | 62708453f8904d0f,d69695c720a341a2,5d446ef1991145da,c92083b7ae4a4385,bc7eae8956d541af,9de875a608fa4fcc,0aaa88bc40094572,0a7d5547503e4f0e,e2f8219fbc814bc0,38fe54ed4a85489b |
| a4a | anthropic.claude-fable-5-1 | high | code | 0.90 [0.60,0.98] | 10 | 0 | 1.530 | 0.17 | 26.078/82.777 | e83dfbf2e8584bc9,95e2510d42684898,b8a080cf5ffe40b4,cc1a1d0807fd4148,6dbc6f61f6ac4505,41e9ce0e6163434e,94b180ffb7ea44aa,cf6eed8bef0a43e7,d15bf8b7b989485f,82322641025e4c5d |
| a4a | anthropic.claude-fable-5-1 | high | gpqa | 0.90 [0.60,0.98] | 10 | 0 | 0.612 | 0.068 | 8.392/65.31 | b4cfbbce9ba14a39,3b850000beba4e17,f8be5a5100f14114,1e8b1f051d084f06,25c9c7556d88438e,73e672003db44f08,784dfcd1966d441a,1e9abdd0f6694a02,ac46546318da42ff,5bc45824bd8349a4 |
| a4a | anthropic.claude-fable-5-1 | high | math | 1.00 [0.72,1.00] | 10 | 0 | 0.797 | 0.0797 | 15.169/21.481 | aca60a5ca89645dd,653c79409d92451e,b8de15087e274402,8a98841dcae946dd,09166450371a4f50,aedd10f5a4d7438f,0a58eeb6d8b540ec,509cabdb7a3348c5,4c9b7a1e6ad74b0b,e6910f3661de4688 |
| a4b | anthropic.claude-haiku-5-5 | medium | code | 0.90 [0.60,0.98] | 10 | 0 | 0.026 | 0.0029 | 17.879/60.603 | 488ec48817f34dba,da4229e5be4848eb,999b7033ff3a4158,f63a91e4162c4da8,f7e3b0944de043aa,2773392dda6e4a10,a5330e4d9dc84872,4cece8cf07754fb7,f81da35a2d1c4085,a44b6fe039184483 |
| a4b | anthropic.claude-haiku-5-5 | medium | gpqa | 0.90 [0.60,0.98] | 10 | 0 | 0.010 | 0.0011 | 7.805/20.9 | 167998d84f1e4d39,c92e72e0b87e4a18,b29fb6b48a3346ae,75a5d7f803484412,2985226df696416e,98c3270cb9e94519,3e32376328e2485e,248a4d1cc8924da0,0e480480f5824f55,1fe843835160454e |
| a4b | anthropic.claude-haiku-5-5 | medium | math | 1.00 [0.72,1.00] | 10 | 0 | 0.016 | 0.0016 | 9.874/28.854 | ba8fa013c47c4575,e3b4324eb60f4267,a9e0b79975134956,8016db84409241b0,972c3b109d184de9,a6da4af22d9b43a2,2bf89f865eee42e9,573e4c86f64c4dbf,15476da6e2c44a34,e4035e4dfc0e4262 |
| sweep | anthropic.claude-fable-5-1 | low | code | 0.80 [0.49,0.94] | 10 | 0 | 0.435 | 0.0544 | 10.124/18.342 | 8f45923ab9fd4acf,8b0e3448afcc4eb6,12d79eb0aa1b4091,d18a262bb08549ae,38eab32962f442a9,f6ddd125c4db4232,2843368e0bd84ca2,407835ee39e2414c,9d8b21adec944cae,24cd589bb8dc403c |
| sweep | anthropic.claude-fable-5-1 | low | gpqa | 0.80 [0.49,0.94] | 10 | 0 | 0.165 | 0.0206 | 4.843/13.305 | 65ccdb4bdfde4e2e,117db267a956435a,ae0696b15f034c71,31acd089bb8b453b,0e1f32917ada4f17,fc00ff4d73eb44e9,de2af58ffccf4a84,bf994c7be3de494c,9b3d008217fe4d55,204bd787ea5f4b96 |
| sweep | anthropic.claude-fable-5-1 | low | math | 0.90 [0.60,0.98] | 10 | 0 | 1.345 | 0.1494 | 13.446/181.122 | 4ec0cefcef9546cf,6c547c35c1c04d86,f8680bb0dfe1407e,2add560caa1843b8,937ebee49cd148d4,386b134ddb374949,2e5f0a659b274888,48764fd239b3422b,b80de7ffee7b4932,359d7ee991244cf6 |
| sweep | anthropic.claude-fable-5-1 | max | code | 0.70 [0.40,0.89] | 10 | 2 | 6.818 | 0.974 | 52.889/471.596 | 5e064b7dee344d9b,56f290156740404a,fca05f6d279940ce,4f61f86d1db144ee,481a942fba53489f,0e9bd2bc99a54dbb,1bc18d0dcb574448,9b248b04d2bc4221,3e1a6d30765b412e,2cd62a970c0347cf |
| sweep | anthropic.claude-fable-5-1 | max | gpqa | 0.90 [0.60,0.98] | 10 | 0 | 1.525 | 0.1695 | 16.697/212.384 | 9556da43d5644fd7,6def7309a3a14643,2888e54947994c9c,019cbb470c774852,01d88b5eaded4184,1aaff1458c07491f,846995a8bc55470e,06b909d48556422a,4c0ec411561d4983,91f52b05b454421c |
| sweep | anthropic.claude-fable-5-1 | max | math | 0.80 [0.49,0.94] | 10 | 2 | 5.702 | 0.7128 | 48.472/417.175 | f40d752e7d5a4cff,fc3e5d214b604b6d,8ad3e90433224849,aecd26a1d1d14829,f21b197e1c334f0d,8289fbe8d5f64976,59b7dc23a68c449b,c9de21d4e4e345a4,72906ae78cca488e,f1595dee2ec649ca |
| sweep | anthropic.claude-fable-5-1 | medium | code | 0.90 [0.60,0.98] | 10 | 0 | 0.637 | 0.0708 | 12.87/45.948 | 54bb68b0c26e4a31,6ecc29cf6f3c418b,b67424c764da4754,cce7757e466a4509,8cf2282ccc7b42a8,3c1c5834b65b4493,7abba7e7509846e8,e5c863c94e1c41ad,e57e26c289534230,3e22abde365d497e |
| sweep | anthropic.claude-fable-5-1 | medium | gpqa | 0.70 [0.40,0.89] | 10 | 0 | 0.192 | 0.0275 | 5.723/10.115 | 9e1b8e1111984794,a51821cbedaa4f90,2a58422ddd5742fc,939bf6fdaf7942c3,8bba11690d6e4839,7e73edf0965649bc,46d3a37555c548e8,1c27fef5170d419c,35e3e8c7d46745a4,13b202cbf53643ee |
| sweep | anthropic.claude-fable-5-1 | medium | math | 1.00 [0.72,1.00] | 10 | 0 | 1.899 | 0.1899 | 20.965/239.227 | 8f3aa119e94540b4,81b9614503fc498e,0ee9d6e59bc84dea,588883cc386b4329,e60a91ff421f45d8,fa1a2285b66d44df,10627458b0ff4e1a,fdf041b0857948cd,74f9f5c6df9f4536,5466960dcf914d0d |
| sweep | anthropic.claude-fable-5-1 | xhigh | code | 0.80 [0.49,0.94] | 10 | 1 | 6.128 | 0.766 | 35.876/439.234 | b3f1332d885a4474,da0d8da54eba4f13,244353447d0f48a6,06f6596159a948a6,a743de41f2d74ca5,108f0ff1114a45a8,0a6afbea0b644c9d,4e0db883a7094195,e81fb3c514f24b95,f918147c0bdb4e90 |
| sweep | anthropic.claude-fable-5-1 | xhigh | gpqa | 0.90 [0.60,0.98] | 10 | 0 | 0.928 | 0.1031 | 16.348/100.119 | 21d6500b5d704ed8,7b7018f3e5314e36,6b9b02c3785844c0,dec2d4408bba4c6b,d4fc6465dc254830,1dde450f436842cd,7a68d6a65eaf4ffa,d09246e1557d44d3,778a1e96394e4ae9,b151d8828e044b2e |
| sweep | anthropic.claude-fable-5-1 | xhigh | math | 0.90 [0.60,0.98] | 10 | 1 | 4.219 | 0.4688 | 40.627/432.548 | 6aa80e0dab50448b,038378176fdc478a,16d4357daafb4bbb,fbca4ede9dbf48f8,d0d2c94dc7b14b1b,5b4c280135764031,23ab181256ca43cf,b1df267d3dce4a1c,eba03b51898244e6,b70617df81674a4b |
| sweep | anthropic.claude-opus-5-5 | high | code | 0.90 [0.60,0.98] | 10 | 0 | 0.371 | 0.0412 | 14.505/27.673 | 604347328bb44943,2132c4ae70e44511,d333b4cd746c4baa,f8e7d8b2ad174684,c7f584a78b7a4ccb,03498a2fc79843a4,70bcf21b81b34da0,1d1b048c23c5425e,d872f502f9d8409b,a329214e613941f2 |
| sweep | anthropic.claude-opus-5-5 | high | gpqa | 0.90 [0.60,0.98] | 10 | 0 | 0.195 | 0.0216 | 7.021/19.932 | 9e9ae1c8d4f442aa,afeb5aaf74d64ecb,93dd3293d68645ae,811575752c6d4a58,e1f9655e7cdb4cd6,8b768c2b50d44763,33cc0653cb9240df,862dbd7e675f47f1,7bdb3c9921a74cfd,db6a21929a9344b1 |
| sweep | anthropic.claude-opus-5-5 | high | math | 1.00 [0.72,1.00] | 10 | 0 | 0.593 | 0.0593 | 14.495/85.049 | 5dddc513042248cd,c393a771ebd94c2c,f33f73b792bd4808,4f0b1bc674fa43db,a3996eced9054593,b438949e94bc4a67,8711a06c0c154f1d,dbd9814c11ab4d5a,d1d59134d7d64ac0,fe3b636ebd354a55 |
| sweep | anthropic.claude-opus-5-5 | low | code | 0.90 [0.60,0.98] | 10 | 0 | 0.211 | 0.0235 | 9.899/13.635 | de387ed5f7c044bb,ac5b69c031f747c2,b4357a3914a242a8,f98b7b9e2c9b4198,c8d88ede77fb4b4f,f5f20cc270b14a89,52c986cdb52b4a31,33e5b3a0ed564eb1,fdbb6f07571e4d3b,c5137a6f845b4696 |
| sweep | anthropic.claude-opus-5-5 | low | gpqa | 0.90 [0.60,0.98] | 10 | 0 | 0.172 | 0.0191 | 7.321/12.433 | e7710ce4b5434a56,4789bb9bbe0d47ce,0ff093de990a4138,bdc9619e25e84d1d,ac464ade945d45ba,62492913148a42ee,55b7e65d0880498d,ca13fc0e6bb34158,a50f391423de4e31,e4a870259c6c44b4 |
| sweep | anthropic.claude-opus-5-5 | low | math | 1.00 [0.72,1.00] | 10 | 0 | 0.416 | 0.0416 | 14.578/63.674 | 37c888478f214bfd,08882a67d0b54a8a,20eb2f55d3904963,bd8b2668b31f4c9e,9d0453e93bc84a6a,e16ff84a82444214,cd057783314e4e3c,d88a9b16e75e4f90,bc25ef7312ee4615,a427e836b18a48b3 |
| sweep | anthropic.claude-opus-5-5 | max | code | 0.60 [0.31,0.83] | 10 | 4 | 3.808 | 0.6347 | 80.318/305.457 | b146bee071d84479,bb2566e6673b496a,be9f358d80c44cf1,4d32e33fb9424b4f,d0ae5c39c3d349e6,a3519b88047647f1,2782a0b228054ac4,ab97614e68dd49c9,b395cda1d1874ad1,0bcdd94082844fee |
| sweep | anthropic.claude-opus-5-5 | max | gpqa | 0.90 [0.60,0.98] | 10 | 0 | 0.941 | 0.1046 | 13.642/228.057 | 2985fc1ac47545f4,df96df796e7748c2,c28b10e4f5924464,148462b469094583,57c938c34b7641f4,e95029332f1244c3,0cf7a39941984321,7cda26fb47944012,f8f76c49b6c540a7,711135401b164a3f |
| sweep | anthropic.claude-opus-5-5 | max | math | 1.00 [0.72,1.00] | 10 | 0 | 1.640 | 0.164 | 37.798/174.121 | 38684758f90f4e1e,3eb5187bff7a4060,56f2811686b24a7b,f3fc043318944699,8dc12c57651448ba,bbfa9e3428904ab0,d51c34fd928d4c57,976092d9d5424eb2,44723fd7bb4140f9,1bf7f8f33ad145e3 |
| sweep | anthropic.claude-opus-5-5 | xhigh | code | 0.90 [0.60,0.98] | 10 | 0 | 0.798 | 0.0886 | 28.161/109.014 | 43335df44bf546a2,63e9d86839e148ef,4122feb8636640ae,1c36ac268ffc4c06,b1f70cafdbad4f84,5a266450d6754d2e,74bfc4ca4ce84085,7791f8fd4f404b3b,e790edd90ff3452b,44eab413c2cd4b28 |
| sweep | anthropic.claude-opus-5-5 | xhigh | gpqa | 0.90 [0.60,0.98] | 10 | 0 | 0.216 | 0.024 | 7.824/21.975 | 0c34f4d5f1044747,f058fa6822614542,2725d162b2cd42e1,c10421e9ce004217,5602f99a77c946a5,d2491ed11f23438f,0251f7ebf64c4384,f29f79dfc5d14278,5a881b17be924e4a,36a87ffc3c1a487d |
| sweep | anthropic.claude-opus-5-5 | xhigh | math | 1.00 [0.72,1.00] | 10 | 0 | 0.995 | 0.0995 | 21.183/172.41 | dcfe3c6acbfa4a5f,d0a5a2c63f7645f5,95e5a48276b348f4,17c6816346b443e5,293f325715d84632,dbeb86c250364a61,fb0799eb8f0f4f87,cc4e6db9132c45d1,1eb40fdcf3014953,2a021fcc238a4ca8 |
| sweep | openai.gpt-6-astra | high | code | 0.90 [0.60,0.98] | 10 | 0 | 0.803 | 0.0892 | 21.322/74.429 | bd4f0138a12c4489,80d4e03b88ca438b,95e740bc51234adb,86d2f04024f54a7c,783907614ef24899,11e13e73f42f4553,7d74fe130ee241f5,9a2abae0903b448d,d49cf99efb0f48a1,e55c030278114dcc |
| sweep | openai.gpt-6-astra | high | gpqa | 1.00 [0.72,1.00] | 10 | 0 | 0.332 | 0.0332 | 8.954/29.89 | 87a1d615677a4a7a,6a0d59a685194f9a,6975fe4487214990,d93e976f47474f67,1fc2447495054e55,544be143d6494a75,00defd5f748a4dae,c3ad684bc7954973,e5e3743741bc41e1,8f39a579ad7c4570 |
| sweep | openai.gpt-6-astra | high | math | 1.00 [0.72,1.00] | 10 | 0 | 1.034 | 0.1034 | 23.952/99.608 | 31d8922290594e62,54dc99c57986480b,a0987b7a12ad4e21,a7e397f856284e09,fed348e85de14c31,e4df4233d4da4ecc,ca2de83501944779,338d4f0597f84a43,5bab986fc12f45c0,a6e83c7c640f424e |
| sweep | openai.gpt-6-astra | low | code | 0.90 [0.60,0.98] | 10 | 0 | 0.311 | 0.0346 | 7.708/22.413 | cf9d6cb8f3aa4523,acbadab156f04ee0,c64d8b65377840b4,a9eca378f25c47af,0c8c3a9528984f75,c493038565ba4b82,8af0b2a1350d4d18,5033e674f54d44d3,a21d1a813fd94fac,2009b279cfb249dd |
| sweep | openai.gpt-6-astra | low | gpqa | 0.90 [0.60,0.98] | 10 | 0 | 0.165 | 0.0183 | 4.083/19.119 | c1c61f7d3c734ee1,8253ec60248d4ebd,bd606016899d47f7,6c87589abe5547fe,a480eb6921924eef,65de69b5344b4234,32b577f22e044a56,c5c1f8750b944811,05636ef590e7484b,84ceb3bf2e754442 |
| sweep | openai.gpt-6-astra | low | math | 1.00 [0.72,1.00] | 10 | 0 | 0.486 | 0.0486 | 10.996/30.054 | b8f89a1d21e64c9f,7027967a3b184431,7933dc5425d94c4c,e6a4a2b36a834777,481c297eb64b4417,8b387200de8048a3,ae1626646aea4a3a,41bef66202734908,cc717a8fe65040fd,d4f52192d3034b63 |
| sweep | openai.gpt-6-astra | max | code | 0.89 [0.56,0.98] | 9 | 0 | 2.035 | 0.2544 | 48.919/116.361 (2 excl.) | b56c3ad97a994c60,ab5300a6618b46c9,f5d8c20d9c664f3b,f3eeaab24efd42f8,32b89885cfa04cf3,0dadf5d6d1fe425b,4e3c2a713ab74c35,de26961352b24f30,2aaa7145744e462c |
| sweep | openai.gpt-6-astra | max | gpqa | 0.90 [0.60,0.98] | 10 | 0 | 1.058 | 0.1176 | 14.402/165.371 | cdf709408afb4e7f,326a6405b5a846dc,86249e148a874351,6a93ed3e5bdc43a6,89dc06102b0246b8,0d40e891f95d48de,4a280a2bca884e6c,f926166709ea49bb,711e0cb80a8a4baa,f5128818f2e34230 |
| sweep | openai.gpt-6-astra | max | math | 1.00 [0.72,1.00] | 10 | 0 | 2.458 | 0.2458 | 47.597/122.807 (1 excl.) | b74c7b82ea744ce7,c6044e16a3554d0e,44f3ec1f232749ed,cee2b47ad4044cc6,f6fcfcf14b2d46a4,9a9de3fe6714426a,a45091027d714b7b,39aaafa1256044c1,22d592808b944f84,5047626ad9554cd4 |
| sweep | openai.gpt-6-astra | xhigh | code | 0.90 [0.60,0.98] | 10 | 0 | 1.310 | 0.1455 | 33.711/143.931 | 4f505c97632b4e15,ab8c04086fdb47cb,916a31a3b9cc4c4e,6da46642c15044bd,a311f0c635c240d2,175f25af5f4d4c67,cc47546acaa8466b,6dff29cc1d594ad5,ccfca18bf2f44431,b0c3c302dcf5421c |
| sweep | openai.gpt-6-astra | xhigh | gpqa | 1.00 [0.72,1.00] | 10 | 0 | 0.624 | 0.0624 | 12.994/75.627 | 9322d25a7632447d,cb05723d52d248e9,02ceb9705fe04aa9,8fa9e0d577b944b4,07143d5e8c704831,7b517c568f9242ea,f2fdf94eca3c486d,7c27c81e61ab43df,074e3128ce4f40ec,66cbfe3f8c444dc9 |
| sweep | openai.gpt-6-astra | xhigh | math | 1.00 [0.72,1.00] | 10 | 0 | 1.535 | 0.1535 | 30.235/144.525 | 347c6e1e08c4459c,bb32baad4acf4fed,8ab53513faf742b6,363fbd0cb5d345ce,93d7b90a36e64488,907b29cd1f414ac1,92bff5e18c23437b,349c4c491836479b,f23d85b91f9f4a61,984edd3ed87e4632 |

## Co-failure matrix (stage-0, per pair)

| set | A | B | grouping | P(both wrong) | P(A w)*P(B w) | ratio | n |
|---|---|---|---|---|---|---|---|
| code | amazon.nova-2-lite-v1:0 | anthropic.claude-fable-5-1 | cross-lab | 0.10 | 0.07 | 1.43 | 10 |
| code | amazon.nova-2-lite-v1:0 | anthropic.claude-haiku-5-5 | cross-lab | 0.20 | 0.14 | 1.43 | 10 |
| code | amazon.nova-2-lite-v1:0 | anthropic.claude-opus-5-5 | cross-lab | 0.10 | 0.07 | 1.43 | 10 |
| code | amazon.nova-2-lite-v1:0 | anthropic.claude-sonnet-5-5 | cross-lab | 0.20 | 0.14 | 1.43 | 10 |
| code | amazon.nova-2-lite-v1:0 | moonshotai.kimi-k3 | cross-lab | 0.20 | 0.14 | 1.43 | 10 |
| code | amazon.nova-2-lite-v1:0 | openai.gpt-6-astra | cross-lab | 0.10 | 0.07 | 1.43 | 10 |
| code | amazon.nova-2-lite-v1:0 | openai.gpt-6-luna | cross-lab | 0.10 | 0.14 | 0.71 | 10 |
| code | amazon.nova-2-lite-v1:0 | openai.gpt-6.1-sol | cross-lab | 0.10 | 0.07 | 1.43 | 10 |
| code | amazon.nova-2-lite-v1:0 | xai.grok-4.7 | cross-lab | 0.40 | 0.28 | 1.43 | 10 |
| code | anthropic.claude-fable-5-1 | anthropic.claude-haiku-5-5 | within-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | anthropic.claude-fable-5-1 | anthropic.claude-opus-5-5 | within-lab | 0.10 | 0.01 | 10.00 | 10 |
| code | anthropic.claude-fable-5-1 | anthropic.claude-sonnet-5-5 | within-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | anthropic.claude-fable-5-1 | moonshotai.kimi-k3 | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | anthropic.claude-fable-5-1 | openai.gpt-6-astra | cross-lab | 0.10 | 0.01 | 10.00 | 10 |
| code | anthropic.claude-fable-5-1 | openai.gpt-6-luna | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | anthropic.claude-fable-5-1 | openai.gpt-6.1-sol | cross-lab | 0.10 | 0.01 | 10.00 | 10 |
| code | anthropic.claude-fable-5-1 | xai.grok-4.7 | cross-lab | 0.10 | 0.04 | 2.50 | 10 |
| code | anthropic.claude-haiku-5-5 | anthropic.claude-opus-5-5 | within-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | anthropic.claude-haiku-5-5 | anthropic.claude-sonnet-5-5 | within-lab | 0.10 | 0.04 | 2.50 | 10 |
| code | anthropic.claude-haiku-5-5 | moonshotai.kimi-k3 | cross-lab | 0.10 | 0.04 | 2.50 | 10 |
| code | anthropic.claude-haiku-5-5 | openai.gpt-6-astra | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | anthropic.claude-haiku-5-5 | openai.gpt-6-luna | cross-lab | 0.10 | 0.04 | 2.50 | 10 |
| code | anthropic.claude-haiku-5-5 | openai.gpt-6.1-sol | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | anthropic.claude-haiku-5-5 | xai.grok-4.7 | cross-lab | 0.20 | 0.08 | 2.50 | 10 |
| code | anthropic.claude-opus-5-5 | anthropic.claude-sonnet-5-5 | within-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | anthropic.claude-opus-5-5 | moonshotai.kimi-k3 | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | anthropic.claude-opus-5-5 | openai.gpt-6-astra | cross-lab | 0.10 | 0.01 | 10.00 | 10 |
| code | anthropic.claude-opus-5-5 | openai.gpt-6-luna | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | anthropic.claude-opus-5-5 | openai.gpt-6.1-sol | cross-lab | 0.10 | 0.01 | 10.00 | 10 |
| code | anthropic.claude-opus-5-5 | xai.grok-4.7 | cross-lab | 0.10 | 0.04 | 2.50 | 10 |
| code | anthropic.claude-sonnet-5-5 | moonshotai.kimi-k3 | cross-lab | 0.20 | 0.04 | 5.00 | 10 |
| code | anthropic.claude-sonnet-5-5 | openai.gpt-6-astra | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | anthropic.claude-sonnet-5-5 | openai.gpt-6-luna | cross-lab | 0.10 | 0.04 | 2.50 | 10 |
| code | anthropic.claude-sonnet-5-5 | openai.gpt-6.1-sol | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | anthropic.claude-sonnet-5-5 | xai.grok-4.7 | cross-lab | 0.20 | 0.08 | 2.50 | 10 |
| code | moonshotai.kimi-k3 | openai.gpt-6-astra | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | moonshotai.kimi-k3 | openai.gpt-6-luna | cross-lab | 0.10 | 0.04 | 2.50 | 10 |
| code | moonshotai.kimi-k3 | openai.gpt-6.1-sol | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | moonshotai.kimi-k3 | xai.grok-4.7 | cross-lab | 0.20 | 0.08 | 2.50 | 10 |
| code | openai.gpt-6-astra | openai.gpt-6-luna | within-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | openai.gpt-6-astra | openai.gpt-6.1-sol | within-lab | 0.10 | 0.01 | 10.00 | 10 |
| code | openai.gpt-6-astra | xai.grok-4.7 | cross-lab | 0.10 | 0.04 | 2.50 | 10 |
| code | openai.gpt-6-luna | openai.gpt-6.1-sol | within-lab | 0.10 | 0.02 | 5.00 | 10 |
| code | openai.gpt-6-luna | xai.grok-4.7 | cross-lab | 0.10 | 0.08 | 1.25 | 10 |
| code | openai.gpt-6.1-sol | xai.grok-4.7 | cross-lab | 0.10 | 0.04 | 2.50 | 10 |
| gpqa | amazon.nova-2-lite-v1:0 | anthropic.claude-fable-5-1 | cross-lab | 0.20 | 0.10 | 2.00 | 10 |
| gpqa | amazon.nova-2-lite-v1:0 | anthropic.claude-haiku-5-5 | cross-lab | 0.20 | 0.20 | 1.00 | 10 |
| gpqa | amazon.nova-2-lite-v1:0 | anthropic.claude-opus-5-5 | cross-lab | 0.10 | 0.05 | 2.00 | 10 |
| gpqa | amazon.nova-2-lite-v1:0 | anthropic.claude-sonnet-5-5 | cross-lab | 0.10 | 0.10 | 1.00 | 10 |
| gpqa | amazon.nova-2-lite-v1:0 | moonshotai.kimi-k3 | cross-lab | 0.10 | 0.05 | 2.00 | 10 |
| gpqa | amazon.nova-2-lite-v1:0 | openai.gpt-6-astra | cross-lab | 0.10 | 0.05 | 2.00 | 10 |
| gpqa | amazon.nova-2-lite-v1:0 | openai.gpt-6-luna | cross-lab | 0.20 | 0.15 | 1.33 | 10 |
| gpqa | amazon.nova-2-lite-v1:0 | openai.gpt-6.1-sol | cross-lab | 0.10 | 0.10 | 1.00 | 10 |
| gpqa | amazon.nova-2-lite-v1:0 | xai.grok-4.7 | cross-lab | 0.10 | 0.15 | 0.67 | 10 |
| gpqa | anthropic.claude-fable-5-1 | anthropic.claude-haiku-5-5 | within-lab | 0.20 | 0.08 | 2.50 | 10 |
| gpqa | anthropic.claude-fable-5-1 | anthropic.claude-opus-5-5 | within-lab | 0.10 | 0.02 | 5.00 | 10 |
| gpqa | anthropic.claude-fable-5-1 | anthropic.claude-sonnet-5-5 | within-lab | 0.10 | 0.04 | 2.50 | 10 |
| gpqa | anthropic.claude-fable-5-1 | moonshotai.kimi-k3 | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| gpqa | anthropic.claude-fable-5-1 | openai.gpt-6-astra | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| gpqa | anthropic.claude-fable-5-1 | openai.gpt-6-luna | cross-lab | 0.20 | 0.06 | 3.33 | 10 |
| gpqa | anthropic.claude-fable-5-1 | openai.gpt-6.1-sol | cross-lab | 0.10 | 0.04 | 2.50 | 10 |
| gpqa | anthropic.claude-fable-5-1 | xai.grok-4.7 | cross-lab | 0.10 | 0.06 | 1.67 | 10 |
| gpqa | anthropic.claude-haiku-5-5 | anthropic.claude-opus-5-5 | within-lab | 0.10 | 0.04 | 2.50 | 10 |
| gpqa | anthropic.claude-haiku-5-5 | anthropic.claude-sonnet-5-5 | within-lab | 0.20 | 0.08 | 2.50 | 10 |
| gpqa | anthropic.claude-haiku-5-5 | moonshotai.kimi-k3 | cross-lab | 0.10 | 0.04 | 2.50 | 10 |
| gpqa | anthropic.claude-haiku-5-5 | openai.gpt-6-astra | cross-lab | 0.10 | 0.04 | 2.50 | 10 |
| gpqa | anthropic.claude-haiku-5-5 | openai.gpt-6-luna | cross-lab | 0.30 | 0.12 | 2.50 | 10 |
| gpqa | anthropic.claude-haiku-5-5 | openai.gpt-6.1-sol | cross-lab | 0.20 | 0.08 | 2.50 | 10 |
| gpqa | anthropic.claude-haiku-5-5 | xai.grok-4.7 | cross-lab | 0.20 | 0.12 | 1.67 | 10 |
| gpqa | anthropic.claude-opus-5-5 | anthropic.claude-sonnet-5-5 | within-lab | 0.10 | 0.02 | 5.00 | 10 |
| gpqa | anthropic.claude-opus-5-5 | moonshotai.kimi-k3 | cross-lab | 0.10 | 0.01 | 10.00 | 10 |
| gpqa | anthropic.claude-opus-5-5 | openai.gpt-6-astra | cross-lab | 0.10 | 0.01 | 10.00 | 10 |
| gpqa | anthropic.claude-opus-5-5 | openai.gpt-6-luna | cross-lab | 0.10 | 0.03 | 3.33 | 10 |
| gpqa | anthropic.claude-opus-5-5 | openai.gpt-6.1-sol | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| gpqa | anthropic.claude-opus-5-5 | xai.grok-4.7 | cross-lab | 0.10 | 0.03 | 3.33 | 10 |
| gpqa | anthropic.claude-sonnet-5-5 | moonshotai.kimi-k3 | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| gpqa | anthropic.claude-sonnet-5-5 | openai.gpt-6-astra | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| gpqa | anthropic.claude-sonnet-5-5 | openai.gpt-6-luna | cross-lab | 0.20 | 0.06 | 3.33 | 10 |
| gpqa | anthropic.claude-sonnet-5-5 | openai.gpt-6.1-sol | cross-lab | 0.20 | 0.04 | 5.00 | 10 |
| gpqa | anthropic.claude-sonnet-5-5 | xai.grok-4.7 | cross-lab | 0.20 | 0.06 | 3.33 | 10 |
| gpqa | moonshotai.kimi-k3 | openai.gpt-6-astra | cross-lab | 0.10 | 0.01 | 10.00 | 10 |
| gpqa | moonshotai.kimi-k3 | openai.gpt-6-luna | cross-lab | 0.10 | 0.03 | 3.33 | 10 |
| gpqa | moonshotai.kimi-k3 | openai.gpt-6.1-sol | cross-lab | 0.10 | 0.02 | 5.00 | 10 |
| gpqa | moonshotai.kimi-k3 | xai.grok-4.7 | cross-lab | 0.10 | 0.03 | 3.33 | 10 |
| gpqa | openai.gpt-6-astra | openai.gpt-6-luna | within-lab | 0.10 | 0.03 | 3.33 | 10 |
| gpqa | openai.gpt-6-astra | openai.gpt-6.1-sol | within-lab | 0.10 | 0.02 | 5.00 | 10 |
| gpqa | openai.gpt-6-astra | xai.grok-4.7 | cross-lab | 0.10 | 0.03 | 3.33 | 10 |
| gpqa | openai.gpt-6-luna | openai.gpt-6.1-sol | within-lab | 0.20 | 0.06 | 3.33 | 10 |
| gpqa | openai.gpt-6-luna | xai.grok-4.7 | cross-lab | 0.20 | 0.09 | 2.22 | 10 |
| gpqa | openai.gpt-6.1-sol | xai.grok-4.7 | cross-lab | 0.20 | 0.06 | 3.33 | 10 |
| math | amazon.nova-2-lite-v1:0 | anthropic.claude-fable-5-1 | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | amazon.nova-2-lite-v1:0 | anthropic.claude-haiku-5-5 | cross-lab | 0.00 | 0.06 | 0.00 | 10 |
| math | amazon.nova-2-lite-v1:0 | anthropic.claude-opus-5-5 | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | amazon.nova-2-lite-v1:0 | anthropic.claude-sonnet-5-5 | cross-lab | 0.00 | 0.03 | 0.00 | 10 |
| math | amazon.nova-2-lite-v1:0 | moonshotai.kimi-k3 | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | amazon.nova-2-lite-v1:0 | openai.gpt-6-astra | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | amazon.nova-2-lite-v1:0 | openai.gpt-6-luna | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | amazon.nova-2-lite-v1:0 | openai.gpt-6.1-sol | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | amazon.nova-2-lite-v1:0 | xai.grok-4.7 | cross-lab | 0.30 | 0.15 | 2.00 | 10 |
| math | anthropic.claude-fable-5-1 | anthropic.claude-haiku-5-5 | within-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-fable-5-1 | anthropic.claude-opus-5-5 | within-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-fable-5-1 | anthropic.claude-sonnet-5-5 | within-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-fable-5-1 | moonshotai.kimi-k3 | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-fable-5-1 | openai.gpt-6-astra | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-fable-5-1 | openai.gpt-6-luna | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-fable-5-1 | openai.gpt-6.1-sol | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-fable-5-1 | xai.grok-4.7 | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-haiku-5-5 | anthropic.claude-opus-5-5 | within-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-haiku-5-5 | anthropic.claude-sonnet-5-5 | within-lab | 0.00 | 0.02 | 0.00 | 10 |
| math | anthropic.claude-haiku-5-5 | moonshotai.kimi-k3 | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-haiku-5-5 | openai.gpt-6-astra | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-haiku-5-5 | openai.gpt-6-luna | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-haiku-5-5 | openai.gpt-6.1-sol | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-haiku-5-5 | xai.grok-4.7 | cross-lab | 0.10 | 0.10 | 1.00 | 10 |
| math | anthropic.claude-opus-5-5 | anthropic.claude-sonnet-5-5 | within-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-opus-5-5 | moonshotai.kimi-k3 | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-opus-5-5 | openai.gpt-6-astra | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-opus-5-5 | openai.gpt-6-luna | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-opus-5-5 | openai.gpt-6.1-sol | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-opus-5-5 | xai.grok-4.7 | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-sonnet-5-5 | moonshotai.kimi-k3 | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-sonnet-5-5 | openai.gpt-6-astra | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-sonnet-5-5 | openai.gpt-6-luna | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-sonnet-5-5 | openai.gpt-6.1-sol | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | anthropic.claude-sonnet-5-5 | xai.grok-4.7 | cross-lab | 0.00 | 0.05 | 0.00 | 10 |
| math | moonshotai.kimi-k3 | openai.gpt-6-astra | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | moonshotai.kimi-k3 | openai.gpt-6-luna | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | moonshotai.kimi-k3 | openai.gpt-6.1-sol | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | moonshotai.kimi-k3 | xai.grok-4.7 | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | openai.gpt-6-astra | openai.gpt-6-luna | within-lab | 0.00 | 0.00 | n/a | 10 |
| math | openai.gpt-6-astra | openai.gpt-6.1-sol | within-lab | 0.00 | 0.00 | n/a | 10 |
| math | openai.gpt-6-astra | xai.grok-4.7 | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | openai.gpt-6-luna | openai.gpt-6.1-sol | within-lab | 0.00 | 0.00 | n/a | 10 |
| math | openai.gpt-6-luna | xai.grok-4.7 | cross-lab | 0.00 | 0.00 | n/a | 10 |
| math | openai.gpt-6.1-sol | xai.grok-4.7 | cross-lab | 0.00 | 0.00 | n/a | 10 |

Item ids per pair: record_groups.json (cofail_* keys).

## Accuracy vs cost

Points: acc_vs_cost.csv. matplotlib not installed: CSV only.
