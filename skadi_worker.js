/**
 * ==========================================================================
 * ♟️ 스카디 체스 백그라운드 Web Worker (Skadi Chess AI Worker)
 * 브라우저 UI 스레드 블로킹 방지 및 백그라운드 Minimax + Alpha-Beta Pruning 탐색
 * ==========================================================================
 */
// 기물 기본 가치 (평가 함수용)
const PIECE_VALUES = {
    'p': 100,
    'n': 320,
    'b': 330,
    'r': 500,
    'q': 900,
    'k': 20000
};

// 기물별 위치 가중치 매트릭스 (Piece-Square Tables: 중앙 점유 및 효율적 배치 평가)
const PST = {
    p: [
        [0,  0,  0,  0,  0,  0,  0,  0],
        [50, 50, 50, 50, 50, 50, 50, 50],
        [10, 10, 20, 30, 30, 20, 10, 10],
        [ 5,  5, 10, 27, 27, 10,  5,  5],
        [ 0,  0,  0, 25, 25,  0,  0,  0],
        [ 5, -5,-10,  0,  0,-10, -5,  5],
        [ 5, 10, 10,-25,-25, 10, 10,  5],
        [ 0,  0,  0,  0,  0,  0,  0,  0]
    ],
    n: [
        [-50,-40,-30,-30,-30,-30,-40,-50],
        [-40,-20,  0,  0,  0,  0,-20,-40],
        [-30,  0, 10, 15, 15, 10,  0,-30],
        [-30,  5, 15, 20, 20, 15,  5,-30],
        [-30,  0, 15, 20, 20, 15,  0,-30],
        [-30,  5, 10, 15, 15, 10,  5,-30],
        [-40,-20,  0,  5,  5,  0,-20,-40],
        [-50,-40,-30,-30,-30,-30,-40,-50]
    ],
    b: [
        [-20,-10,-10,-10,-10,-10,-10,-20],
        [-10,  0,  0,  0,  0,  0,  0,-10],
        [-10,  0,  5, 10, 10,  5,  0,-10],
        [-10,  5,  5, 10, 10,  5,  5,-10],
        [-10,  0, 10, 10, 10, 10,  0,-10],
        [-10, 10, 10, 10, 10, 10, 10,-10],
        [-10,  5,  0,  0,  0,  0,  5,-10],
        [-20,-10,-10,-10,-10,-10,-10,-20]
    ],
    r: [
        [ 0,  0,  0,  0,  0,  0,  0,  0],
        [ 5, 10, 10, 10, 10, 10, 10,  5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [ 0,  0,  0,  5,  5,  0,  0,  0]
    ],
    q: [
        [-20,-10,-10, -5, -5,-10,-10,-20],
        [-10,  0,  0,  0,  0,  0,  0,-10],
        [-10,  0,  5,  5,  5,  5,  0,-10],
        [ -5,  0,  5,  5,  5,  5,  0, -5],
        [  0,  0,  5,  5,  5,  5,  0, -5],
        [-10,  5,  5,  5,  5,  5,  0,-10],
        [-10,  0,  5,  0,  0,  0,  0,-10],
        [-20,-10,-10, -5, -5,-10,-10,-20]
    ],
    k: [
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-20,-30,-30,-40,-40,-30,-30,-20],
        [-10,-20,-20,-20,-20,-20,-20,-10],
        [ 20, 20,  0,  0,  0,  0, 20, 20],
        [ 20, 30, 10,  0,  0, 10, 30, 20]
    ]
};

// 24시간 클라우드/오프라인 무중단 지원용 내장 마스터 전술 데이터베이스 풀
const DEFAULT_TACTICS_FALLBACK = [
    {
        id: "sicilian",
        name: "시실리안 디펜스 (Sicilian Defense)",
        side: "b",
        desc: "흑의 강력하고 날카로운 카운터 공격 전술로, 승률이 가장 높은 명전술입니다.",
        moves: ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4", "c5d4"],
        quote: "이번 판은 [시실리안 디펜스]다! 네 중앙 파운을 잘게 쪼개주마!"
    },
    {
        id: "ruy_lopez",
        name: "루이 로페즈 전술 (Ruy Lopez)",
        side: "w",
        desc: "백의 정석적이고 거친 견제 오프닝 전술로, 상대 킹사이드 공간을 전면 압박합니다.",
        moves: ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6"],
        quote: "[루이 로페즈] 전술을 가동한다! 네 나이트 핀을 걸어서 꼼짝 못 하게 만들어주마."
    },
    {
        id: "queens_gambit",
        name: "퀸즈 갬빗 (Queen's Gambit)",
        side: "w",
        desc: "백의 강력한 중앙 희생 공격 전술로, 주도권을 쥐고 보드를 지배합니다.",
        moves: ["d2d4", "d7d5", "c2c4", "e7e6", "b1c3", "g8f6"],
        quote: "[퀸즈 갬빗] 전술 투입! 이 미끼 파운을 물 것인가, 아니면 도망칠 것인가?"
    },
    {
        id: "kings_indian",
        name: "킹스 인디언 디펜스 (King's Indian)",
        side: "b",
        desc: "흑의 변칙 섀도우 복싱 카운터 전술로, 킹사이드 피앙케토 비숍 배치를 활용합니다.",
        moves: ["d2d4", "g8f6", "c2c4", "g7g6", "b1c3", "f8g7"],
        quote: "[킹스 인디언 디펜스] 발동! 내 요새 비숍의 빔을 감당해봐라 마스터!"
    },
    {
        id: "french_defense",
        name: "프렌치 디펜스 (French Defense)",
        side: "b",
        desc: "흑의 탄탄한 철벽 방어 후 퀸사이드 반격 전술입니다.",
        moves: ["e2e4", "e7e6", "d2d4", "d7d5", "e4e5", "c7c5"],
        quote: "[프렌치 디펜스] 사수! 뚫기 힘든 진형으로 네 공격을 무력화시킨다."
    },
    {
        id: "caro_kann",
        name: "카로-칸 디펜스 (Caro-Kann Defense)",
        side: "b",
        desc: "흑의 차분하고 안정적인 파운 체인 방어 전술입니다.",
        moves: ["e2e4", "c7c6", "d2d4", "d7d5", "b1c3", "d5e4"],
        quote: "[카로-칸 디펜스] 세팅 완료! 아무리 쏴봐야 내 방어선엔 흠집도 안 난다."
    },
    {
        id: "italian_game",
        name: "이탈리안 게임 (Italian Game)",
        side: "w",
        desc: "백의 클래식하고 치명적인 f7 약점 기습 공격 오프닝입니다.",
        moves: ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5"],
        quote: "[이탈리안 게임] 발진! f7 약점 타일로 전면 돌격이다!"
    },
    {
        id: "english_opening",
        name: "잉글리시 오프닝 (English Opening)",
        side: "w",
        desc: "c4 파운으로 측면 공간을 조종하는 현대 체스 전술입니다.",
        moves: ["c2c4", "e7e5", "b1c3", "g8f6", "g2g3", "d7d5"],
        quote: "[잉글리시 오프닝] 전개! 측면에서 천천히 조여오는 압박을 느껴봐라."
    },
    {
        id: "scandinavian",
        name: "스칸디나비안 기습 (Scandinavian Defense)",
        side: "b",
        desc: "1...d7-d5 즉각 중앙 반격으로 판세를 흔드는 기습 전술입니다.",
        moves: ["e2e4", "d7d5", "e4d5", "d8d5", "b1c3", "d8a5"],
        quote: "[스칸디나비안 기습]! 첫 수부터 네 중앙을 박살 내주마!"
    },
    {
        id: "vienna_game",
        name: "비엔나 기습 갬빗 (Vienna Game)",
        side: "w",
        desc: "f4 파운을 이용해 상대를 무섭게 밀어붙이는 기습 갬빗 공격입니다.",
        moves: ["e2e4", "e7e5", "b1c3", "g8f6", "f2f4", "d7d5"],
        quote: "[비엔나 갬빗] 기습! 파운 공격으로 네 전열을 붕괴시킨다."
    }
];

/**
 * 2. 체스 코어 게임 클래스 (ChessGame)
 */
class ChessGame {
    constructor() {
        this.resetGame();
    }

    resetGame() {
        this.board = [
            ['bR', 'bN', 'bB', 'bQ', 'bK', 'bB', 'bN', 'bR'],
            ['bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP'],
            [null, null, null, null, null, null, null, null],
            [null, null, null, null, null, null, null, null],
            [null, null, null, null, null, null, null, null],
            [null, null, null, null, null, null, null, null],
            ['wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP'],
            ['wR', 'wN', 'wB', 'wQ', 'wK', 'wB', 'wN', 'wR']
        ];

        this.turn = 'w';
        this.castling = {
            w: { kingSide: true, queenSide: true },
            b: { kingSide: true, queenSide: true }
        };
        this.enPassant = null;
        this.moveHistory = [];
        this.capturedPieces = { w: [], b: [] };
        this.isGameOver = false;
        this.winner = null;
        this.lastMove = null;
        this.positionHistory = [this.getBoardHash()];
        this.undoStack = [];
        this.boardHistory = [JSON.parse(JSON.stringify(this.board))];
    }

    getBoardHash() {
        let hash = `${this.turn}:`;
        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                hash += (this.board[r][c] || '.');
            }
        }
        return hash;
    }

    getPiece(r, c) {
        if (r < 0 || r > 7 || c < 0 || c > 7) return null;
        return this.board[r][c];
    }

    /**
     * 유효 이동 목록 생성 (체크 검증 포함)
     */
    generateLegalMoves(color = this.turn) {
        const pseudoMoves = this.generatePseudoMoves(color);
        const legalMoves = [];

        for (let i = 0; i < pseudoMoves.length; i++) {
            const move = pseudoMoves[i];
            const undoState = this.makeMove(move, true);
            if (!this.isKingInCheck(color)) {
                legalMoves.push(move);
            }
            this.undoMove(undoState, true);
        }

        return legalMoves;
    }

    generatePseudoMoves(color) {
        const moves = [];
        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                const piece = this.board[r][c];
                if (piece && piece[0] === color) {
                    const pType = piece[1].toLowerCase();
                    switch (pType) {
                        case 'p': this.getPawnMoves(r, c, color, moves); break;
                        case 'n': this.getKnightMoves(r, c, color, moves); break;
                        case 'b': this.getSlidingMoves(r, c, color, [[-1,-1], [-1,1], [1,-1], [1,1]], moves); break;
                        case 'r': this.getSlidingMoves(r, c, color, [[-1,0], [1,0], [0,-1], [0,1]], moves); break;
                        case 'q': this.getSlidingMoves(r, c, color, [[-1,-1], [-1,1], [1,-1], [1,1], [-1,0], [1,0], [0,-1], [0,1]], moves); break;
                        case 'k': this.getKingMoves(r, c, color, moves); break;
                    }
                }
            }
        }
        return moves;
    }

    getPawnMoves(r, c, color, moves) {
        const dir = color === 'w' ? -1 : 1;
        const startRank = color === 'w' ? 6 : 1;
        const promoRank = color === 'w' ? 0 : 7;

        const nr = r + dir;
        if (nr >= 0 && nr <= 7) {
            if (!this.board[nr][c]) {
                if (nr === promoRank) {
                    ['q', 'r', 'b', 'n'].forEach(p => moves.push({ from: {r, c}, to: {r: nr, c}, promo: p }));
                } else {
                    moves.push({ from: {r, c}, to: {r: nr, c} });
                    const nr2 = r + dir * 2;
                    if (r === startRank && nr2 >= 0 && nr2 <= 7 && !this.board[nr2][c]) {
                        moves.push({ from: {r, c}, to: {r: nr2, c}, isDoublePawn: true });
                    }
                }
            }

            [-1, 1].forEach(dc => {
                const nc = c + dc;
                if (nc >= 0 && nc <= 7) {
                    const target = this.board[nr][nc];
                    if (target && target[0] !== color) {
                        if (nr === promoRank) {
                            ['q', 'r', 'b', 'n'].forEach(p => moves.push({ from: {r, c}, to: {r: nr, c: nc}, promo: p, captured: target }));
                        } else {
                            moves.push({ from: {r, c}, to: {r: nr, c: nc}, captured: target });
                        }
                    } else if (this.enPassant && this.enPassant.r === nr && this.enPassant.c === nc) {
                        const capPiece = color === 'w' ? 'bP' : 'wP';
                        moves.push({ from: {r, c}, to: {r: nr, c: nc}, isEnPassant: true, captured: capPiece });
                    }
                }
            });
        }
    }

    getKnightMoves(r, c, color, moves) {
        const offsets = [[-2,-1],[-2,1],[-1,-2],[-1,2],[1,-2],[1,2],[2,-1],[2,1]];
        offsets.forEach(([dr, dc]) => {
            const nr = r + dr, nc = c + dc;
            if (nr >= 0 && nr <= 7 && nc >= 0 && nc <= 7) {
                const target = this.board[nr][nc];
                if (!target || target[0] !== color) {
                    moves.push({ from: {r, c}, to: {r: nr, c: nc}, captured: target });
                }
            }
        });
    }

    getSlidingMoves(r, c, color, dirs, moves) {
        dirs.forEach(([dr, dc]) => {
            let nr = r + dr, nc = c + dc;
            while (nr >= 0 && nr <= 7 && nc >= 0 && nc <= 7) {
                const target = this.board[nr][nc];
                if (!target) {
                    moves.push({ from: {r, c}, to: {r: nr, c: nc} });
                } else {
                    if (target[0] !== color) {
                        moves.push({ from: {r, c}, to: {r: nr, c: nc}, captured: target });
                    }
                    break;
                }
                nr += dr;
                nc += dc;
            }
        });
    }

    getKingMoves(r, c, color, moves) {
        const dirs = [[-1,-1],[-1,0],[-1,1],[0,-1],[0,1],[1,-1],[1,0],[1,1]];
        dirs.forEach(([dr, dc]) => {
            const nr = r + dr, nc = c + dc;
            if (nr >= 0 && nr <= 7 && nc >= 0 && nc <= 7) {
                const target = this.board[nr][nc];
                if (!target || target[0] !== color) {
                    moves.push({ from: {r, c}, to: {r: nr, c: nc}, captured: target });
                }
            }
        });

        if (!this.isSquareAttacked(r, c, color)) {
            const cRights = this.castling[color];
            const rank = color === 'w' ? 7 : 0;

            if (cRights.kingSide && !this.board[rank][5] && !this.board[rank][6]) {
                if (!this.isSquareAttacked(rank, 5, color) && !this.isSquareAttacked(rank, 6, color)) {
                    moves.push({ from: {r, c}, to: {r: rank, c: 6}, isCastling: 'kingSide' });
                }
            }
            if (cRights.queenSide && !this.board[rank][1] && !this.board[rank][2] && !this.board[rank][3]) {
                if (!this.isSquareAttacked(rank, 2, color) && !this.isSquareAttacked(rank, 3, color)) {
                    moves.push({ from: {r, c}, to: {r: rank, c: 2}, isCastling: 'queenSide' });
                }
            }
        }
    }

    /**
     * 순수 직접 탐색형 타일 공격 검증 (Direct Attack Checking - 재귀호출 0%)
     */
    isSquareAttacked(r, c, defenderColor) {
        const attackerColor = defenderColor === 'w' ? 'b' : 'w';

        // 1. 파운 공격 체크
        const pawnDir = defenderColor === 'w' ? -1 : 1;
        const pr = r + pawnDir;
        if (pr >= 0 && pr <= 7) {
            if (c - 1 >= 0 && this.board[pr][c - 1] === attackerColor + 'P') return true;
            if (c + 1 <= 7 && this.board[pr][c + 1] === attackerColor + 'P') return true;
        }

        // 2. 나이트 공격 체크
        const knightOffsets = [[-2,-1],[-2,1],[-1,-2],[-1,2],[1,-2],[1,2],[2,-1],[2,1]];
        for (let i = 0; i < knightOffsets.length; i++) {
            const [dr, dc] = knightOffsets[i];
            const nr = r + dr, nc = c + dc;
            if (nr >= 0 && nr <= 7 && nc >= 0 && nc <= 7) {
                if (this.board[nr][nc] === attackerColor + 'N') return true;
            }
        }

        // 3. 킹 공격 체크
        const kingDirs = [[-1,-1],[-1,0],[-1,1],[0,-1],[0,1],[1,-1],[1,0],[1,1]];
        for (let i = 0; i < kingDirs.length; i++) {
            const [dr, dc] = kingDirs[i];
            const nr = r + dr, nc = c + dc;
            if (nr >= 0 && nr <= 7 && nc >= 0 && nc <= 7) {
                if (this.board[nr][nc] === attackerColor + 'K') return true;
            }
        }

        // 4. 비숍 & 퀸 대각선 공격 체크
        const diagDirs = [[-1,-1],[-1,1],[1,-1],[1,1]];
        for (let i = 0; i < diagDirs.length; i++) {
            const [dr, dc] = diagDirs[i];
            let nr = r + dr, nc = c + dc;
            while (nr >= 0 && nr <= 7 && nc >= 0 && nc <= 7) {
                const piece = this.board[nr][nc];
                if (piece) {
                    if (piece === attackerColor + 'B' || piece === attackerColor + 'Q') return true;
                    break;
                }
                nr += dr; nc += dc;
            }
        }

        // 5. 룩 & 퀸 직선 공격 체크
        const straightDirs = [[-1,0],[1,0],[0,-1],[0,1]];
        for (let i = 0; i < straightDirs.length; i++) {
            const [dr, dc] = straightDirs[i];
            let nr = r + dr, nc = c + dc;
            while (nr >= 0 && nr <= 7 && nc >= 0 && nc <= 7) {
                const piece = this.board[nr][nc];
                if (piece) {
                    if (piece === attackerColor + 'R' || piece === attackerColor + 'Q') return true;
                    break;
                }
                nr += dr; nc += dc;
            }
        }

        return false;
    }

    findKing(color) {
        const kStr = color + 'K';
        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                if (this.board[r][c] === kStr) return { r, c };
            }
        }
        return null;
    }

    isKingInCheck(color) {
        const kPos = this.findKing(color);
        if (!kPos) return false;
        return this.isSquareAttacked(kPos.r, kPos.c, color);
    }

    /**
     * 수 실행 (makeMove 내부에서는 generateLegalMoves를 결코 호출하지 않음!)
     */
    makeMove(move, isSimulation = false) {
        let evalBefore = 0;
        if (!isSimulation) evalBefore = this.evaluateBoard();

        const { from, to, promo, isCastling, isEnPassant, isDoublePawn } = move;
        const piece = this.board[from.r][from.c];
        const captured = this.board[to.r][to.c];

        const undoState = {
            move,
            piece,
            captured,
            castling: JSON.parse(JSON.stringify(this.castling)),
            enPassant: this.enPassant ? { ...this.enPassant } : null,
            turn: this.turn,
            lastMove: this.lastMove
        };

        this.board[to.r][to.c] = piece;
        this.board[from.r][from.c] = null;

        if (promo) {
            this.board[to.r][to.c] = this.turn + promo.toUpperCase();
        }

        if (isCastling) {
            const rank = from.r;
            if (isCastling === 'kingSide') {
                this.board[rank][5] = this.board[rank][7];
                this.board[rank][7] = null;
            } else if (isCastling === 'queenSide') {
                this.board[rank][3] = this.board[rank][0];
                this.board[rank][0] = null;
            }
        }

        if (isEnPassant) {
            const capRank = from.r;
            undoState.enPassantCaptured = this.board[capRank][to.c];
            this.board[capRank][to.c] = null;
        }

        if (isDoublePawn) {
            this.enPassant = { r: (from.r + to.r) / 2, c: from.c };
        } else {
            this.enPassant = null;
        }

        if (piece === 'wK') this.castling.w = { kingSide: false, queenSide: false };
        if (piece === 'bK') this.castling.b = { kingSide: false, queenSide: false };
        if (from.r === 7 && from.c === 0) this.castling.w.queenSide = false;
        if (from.r === 7 && from.c === 7) this.castling.w.kingSide = false;
        if (from.r === 0 && from.c === 0) this.castling.b.queenSide = false;
        if (from.r === 0 && from.c === 7) this.castling.b.kingSide = false;

        this.lastMove = move;

        if (!isSimulation) {
            let evalAfter = this.evaluateBoard();
            let delta = this.turn === 'w' ? (evalAfter - evalBefore) : (evalBefore - evalAfter);
            
            let annotation = '';
            if (delta <= -250) annotation = '??';
            else if (delta <= -100) annotation = '?';
            else if (delta <= -30) annotation = '?!';
            else if (delta >= 150 && !captured) annotation = '!!';
            else if (delta >= 80) annotation = '!';

            let san = this.formatSAN(move, piece, captured) + annotation;

            if (captured) {
                this.capturedPieces[this.turn].push(captured);
            } else if (isEnPassant) {
                this.capturedPieces[this.turn].push(undoState.enPassantCaptured);
            }
            this.moveHistory.push(san);
            this.undoStack.push(undoState);
            this.boardHistory.push(JSON.parse(JSON.stringify(this.board)));
            this.turn = this.turn === 'w' ? 'b' : 'w';
        } else {
            this.turn = this.turn === 'w' ? 'b' : 'w';
        }

        return undoState;
    }

    /**
     * 실제 게임 진행 시에만 체크메이트/스테일메이트, 3회 동형 반복 및 120수 제한 검사
     */
    checkGameOver() {
        // 120수 달성 시 자동 무승부 처리 (장기전 소진 방지 룰)
        if (this.moveHistory.length >= 120) {
            this.isGameOver = true;
            this.winner = 'draw';
            return;
        }

        // 3회 동형 반복 무승부 검사 (Threefold Repetition Rule)
        const currentHash = this.getBoardHash();
        this.positionHistory.push(currentHash);
        const matchCount = this.positionHistory.filter(h => h === currentHash).length;
        if (matchCount >= 3) {
            this.isGameOver = true;
            this.winner = 'draw';
            this.drawReason = 'threefold';
            return;
        }

        const nextMoves = this.generateLegalMoves(this.turn);
        if (nextMoves.length === 0) {
            this.isGameOver = true;
            if (this.isKingInCheck(this.turn)) {
                this.winner = this.turn === 'w' ? 'b' : 'w';
            } else {
                this.winner = 'draw';
            }
        }
    }

    undoMove(undoState, isSimulation = false) {
        const { move, piece, captured, castling, enPassant, turn, enPassantCaptured, lastMove } = undoState;
        const { from, to, isCastling, isEnPassant } = move;

        this.board[from.r][from.c] = piece;
        this.board[to.r][to.c] = captured;
        this.castling = castling;
        this.enPassant = enPassant;
        this.turn = turn;
        this.lastMove = lastMove;

        if (!isSimulation) {
            if (captured || isEnPassant) {
                this.capturedPieces[this.turn].pop();
            }
        }

        if (isCastling) {
            const rank = from.r;
            if (isCastling === 'kingSide') {
                this.board[rank][7] = this.board[rank][5];
                this.board[rank][5] = null;
            } else if (isCastling === 'queenSide') {
                this.board[rank][0] = this.board[rank][3];
                this.board[rank][3] = null;
            }
        }

        if (isEnPassant) {
            this.board[from.r][to.c] = enPassantCaptured;
        }

        if (!isSimulation) {
            this.isGameOver = false;
            this.winner = null;
            this.moveHistory.pop();
            if (captured || isEnPassant) {
                this.capturedPieces[this.turn].pop();
            }
        }
    }

    formatSAN(move, piece, captured) {
        const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
        const fromStr = `${files[move.from.c]}${8 - move.from.r}`;
        const toStr = `${files[move.to.c]}${8 - move.to.r}`;
        const pSymbol = piece[1].toUpperCase() === 'P' ? '' : piece[1].toUpperCase();
        const capSymbol = captured || move.isEnPassant ? 'x' : '-';
        return `${pSymbol}${fromStr}${capSymbol}${toStr}`;
    }

    evaluateBoard() {
        let score = 0;
        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                const piece = this.board[r][c];
                if (piece) {
                    const color = piece[0];
                    const type = piece[1].toLowerCase();
                    const val = PIECE_VALUES[type] + (PST[type] ? (color === 'w' ? PST[type][r][c] : PST[type][7 - r][c]) : 0);
                    score += (color === 'w' ? val : -val);
                }
            }
        }
        return score;
    }
}

/**
 * 3. 스카디 AI 엔진 (Minimax + Alpha-Beta Pruning)
 */
class SkadiEngine {
    constructor(game) {
        this.game = game;
    }

    /**
     * 크롤링된 오프닝 전술 기보(Opening Book) 수순을 초반 수로 실전 보드 집행
     */
    getOpeningBookMove(color, tactic) {
        if (!tactic || !tactic.moves || tactic.moves.length === 0) return null;
        
        const historyLen = this.game.moveHistory.length;
        if (historyLen >= tactic.moves.length) return null;
        
        const targetUci = tactic.moves[historyLen];
        if (!targetUci || targetUci.length < 4) return null;
        
        const files = {'a':0, 'b':1, 'c':2, 'd':3, 'e':4, 'f':5, 'g':6, 'h':7};
        const fromC = files[targetUci[0]];
        const fromR = 8 - parseInt(targetUci[1], 10);
        const toC = files[targetUci[2]];
        const toR = 8 - parseInt(targetUci[3], 10);
        
        const legalMoves = this.game.generateLegalMoves(color);
        const matchedMove = legalMoves.find(m => m.from.r === fromR && m.from.c === fromC && m.to.r === toR && m.to.c === toC);
        
        return matchedMove || null;
    }

    getBestMove(depth = 2, color = 'b', tactic = null) {
        // 1. 크롤링 오프닝 기보(Opening Book)가 존재할 경우 초반 수로 실전 보드 집행
        if (tactic) {
            const bookMove = this.getOpeningBookMove(color, tactic);
            if (bookMove) return bookMove;
        }

        const legalMoves = this.game.generateLegalMoves(color);
        if (legalMoves.length === 0) return null;

        // 캡처 우선 정렬 (알파베타 가지치기 최적화)
        legalMoves.sort((a, b) => (b.captured ? 1 : 0) - (a.captured ? 1 : 0));

        let bestMove = legalMoves[0];
        let bestScore = color === 'w' ? -Infinity : Infinity;

        for (let i = 0; i < legalMoves.length; i++) {
            const move = legalMoves[i];
            const undoState = this.game.makeMove(move, true);
            let score = this.minimax(depth - 1, -Infinity, Infinity, color !== 'w');
            this.game.undoMove(undoState, true);

            // 무의미하게 이전 위치로 왔다갔다하는 셔플 루프(Shuffle Loop) 감점 페널티 (-250점)
            if (this.game.lastMove && move.to.r === this.game.lastMove.from.r && move.to.c === this.game.lastMove.from.c) {
                if (color === 'w') score -= 250;
                else score += 250;
            }

            if (color === 'w') {
                if (score > bestScore) {
                    bestScore = score;
                    bestMove = move;
                }
            } else {
                if (score < bestScore) {
                    bestScore = score;
                    bestMove = move;
                }
            }
        }

        return bestMove;
    }

    minimax(depth, alpha, beta, isMaximizing) {
        if (depth <= 0 || this.game.isGameOver) {
            return this.game.evaluateBoard();
        }

        const color = isMaximizing ? 'w' : 'b';
        const moves = this.game.generateLegalMoves(color);

        if (moves.length === 0) {
            if (this.game.isKingInCheck(color)) {
                return isMaximizing ? -99999 : 99999;
            }
            return 0;
        }

        if (isMaximizing) {
            let maxEval = -Infinity;
            for (let i = 0; i < moves.length; i++) {
                const undoState = this.game.makeMove(moves[i], true);
                const evalScore = this.minimax(depth - 1, alpha, beta, false);
                this.game.undoMove(undoState, true);
                maxEval = Math.max(maxEval, evalScore);
                alpha = Math.max(alpha, evalScore);
                if (beta <= alpha) break;
            }
            return maxEval;
        } else {
            let minEval = Infinity;
            for (let i = 0; i < moves.length; i++) {
                const undoState = this.game.makeMove(moves[i], true);
                const evalScore = this.minimax(depth - 1, alpha, beta, true);
                this.game.undoMove(undoState, true);
                minEval = Math.min(minEval, evalScore);
                beta = Math.min(beta, evalScore);
                if (beta <= alpha) break;
            }
            return minEval;
        }
    }
}



// ==========================================================================
// Web Worker 메시지 리스너 (UI 스레드와 비동기 통신)
// ==========================================================================
self.onmessage = function(e) {
    const data = e.data;
    if (!data) return;

    if (data.type === 'CALCULATE_BEST_MOVE') {
        const game = new ChessGame();
        game.board = data.board;
        game.turn = data.turn;
        game.castling = data.castling || { w: { kingSide: true, queenSide: true }, b: { kingSide: true, queenSide: true } };
        game.enPassant = data.enPassant || null;
        game.moveHistory = data.moveHistory || [];

        const engine = new SkadiEngine(game);
        const botMove = engine.getBestMove(data.depth, data.color, data.tactic);

        self.postMessage({
            type: 'BEST_MOVE_RESULT',
            botMove: botMove,
            jobId: data.jobId,
            userMove: data.userMove,
            isUserBlunder: data.isUserBlunder
        });
    } else if (data.type === 'CALCULATE_HINT') {
        const game = new ChessGame();
        game.board = data.board;
        game.turn = data.turn;
        game.castling = data.castling || { w: { kingSide: true, queenSide: true }, b: { kingSide: true, queenSide: true } };
        game.enPassant = data.enPassant || null;
        game.moveHistory = data.moveHistory || [];

        const engine = new SkadiEngine(game);
        const hintMove = engine.getBestMove(data.depth || 3, data.color);

        self.postMessage({
            type: 'HINT_RESULT',
            hintMove: hintMove,
            jobId: data.jobId
        });
    }
};
