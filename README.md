# DeFi-semantic

- DeFi에서 발생하는 Price Manipulation Attack 탐지를 위한 시스템
- tx에 대해 semantic 추출 및 자금 이동에 대한 그래프 생성

### ToDos

- [X] alchemy 기반 tx receipt 추출
- [X] receipt에서 address 추출하여 EOA/CA 구분. CA에 대해 abi 추출

  - [X] proxy인 경우 implementation 주소 찾아 abi 복구
- [X] 각 event log에 대해 symbol, decimal 복구
- [X] semantic 그래프 생성 시, src / dst / amount 식별하여 엣지 그리기

  - [X] 무조건 inputs 내부 파라미터로 src->dst 관계가 형성되지 않음
  - [X] 현재는 파라미터로 엣지를 그려서 누락되는 이벤트가 존재함
    0409) 프로토콜 별로 자금 이동과 관련된 함수의 src - dst 관계에 대해 json에 정의해뒀음
- [ ] address에 대한 라벨링
- [ ] semantic에 대해 DEX, Lending Protocol 별 이벤트 abstract 필요
- [ ] benign tx vs malicious tx 수집
