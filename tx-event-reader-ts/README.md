# DeFi-semantic

- DeFi에서 발생하는 Price Manipulation Attack 탐지를 위한 시스템 
- tx에 대해 semantic 추출 및 자금 이동에 대한 그래프 생성

### ToDos

- [x] alchemy 기반 tx receipt 추출

- [x] receipt에서 address 추출하여 EOA/CA 구분. CA에 대해 abi 추출
    - [x] proxy인 경우 implementation 주소 찾아 abi 복구
- [x] 각 event log에 대해 symbol, decimal 복구
- [ ] address에 대한 라벨링
- [ ] semantic에 대해 DEX, Lending Protocol 별 이벤트 abstract 필요
- [ ] benign tx vs malicious tx 수집 


