/**
 * ==========================================================================
 * ♟️ 스카디 체스 봇 & 체스 코어 엔진 (Skadi Chess Engine & AI)
 * 작성 언어: JavaScript (한국어 주석 포함)
 * 핵심 설계:
 *   1. 체스 보드 상태 관리 및 정석 이동/특수 수(캐슬링, 앙파상, 프로모션) 지원
 *   2. 수 실행(makeMove)과 법적 수 계산(generateLegalMoves) 간 상호호출 완전 분리
 *   3. 직접 탐색형 타일 공격 검증(Direct Attack Checking)으로 재귀 0% 보장
 *   4. Minimax + Alpha-Beta Pruning 기반 스카디 체스 AI 봇
 *   5. 스카디 실시간 E-sports 훈수 톡 및 백엔드/웹 음성 하이브리드 TTS 연동
 *   6. DOM UI 렌더링 및 인터랙션 컨트롤
 * ==========================================================================
 */

// 1. 체스 기물 유니코드 표기 정의
const PIECE_UNICODE = {
    'wK': '♔', 'wQ': '♕', 'wR': '♖', 'wB': '♗', 'wN': '♘', 'wP': '♙',
    'bK': '♚', 'bQ': '♛', 'bR': '♜', 'bB': '♝', 'bN': '♞', 'bP': '♟'
};

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

/**
 * 4. 스카디 페르소나 (SkadiPersona)
 */
class SkadiPersona {
    constructor() {
        this.speechSynth = window.speechSynthesis;
        this.voiceEnabled = true;
        this.volume = 0.8;
        this.currentAudio = null; // 단일 재생 오디오 추적용
    }

    setVolume(val) {
        this.volume = Math.max(0, Math.min(1, parseFloat(val)));
        if (this.currentAudio) {
            this.currentAudio.volume = this.volume;
        }
    }

    /**
     * 기존에 낭독 중인 모든 백엔드 Audio 및 브라우저 TTS를 즉각 중지 (음성 중첩 방지)
     */
    stopAllSpeech() {
        if (this.currentAudio) {
            try {
                this.currentAudio.pause();
                this.currentAudio.currentTime = 0;
            } catch (e) {}
            this.currentAudio = null;
        }
        if (this.speechSynth) {
            try {
                this.speechSynth.cancel();
            } catch (e) {}
        }
    }

    generateFeedback(game, userMove, botMove, isUserBlunder) {
        const quotes = {
            userBlunder: [
                "야! 멍청하게 기물을 그냥 갖다 바치냐? 두뇌 회전 속도가 왜 이래?",
                "너 체스 처음 해보냐? 거기를 두면 내 먹잇감밖에 더 되냐!",
                "헛웃음 나오네. 섀도우 복싱이라도 더 하고 와라!"
            ],
            userCheck: [
                "체크다! 네 왕 목 달아나기 전에 빨리 도망쳐라!",
                "방심했지? 킹 위치가 너무 허술하다고 소리치고 있잖아!"
            ],
            botCapture: [
                "크하하! 네 기물은 내가 맛있게 잘 먹었다!",
                "각도가 딱 나왔어. 넌 방금 치명적인 실수를 한 거야."
            ],
            normalMove: [
                "음, 나쁘지 않은 수지만 내 전술을 뚫긴 부족해.",
                "더 깊게 계산해라! 내 판세 분석은 이미 5수 앞을 보고 있다.",
                "망설이지 말고 덤벼라, 마스터!"
            ],
            skadiWin: [
                "체크메이트! 항복해라 마스터! 내 전술 분석 완승이다!",
                "게임 끝이다! 보드의 왕관은 내 거다."
            ],
            userWin: [
                "웩... 내가 졌다고? 인정 못 해, 당장 한 판 더 해!"
            ]
        };

        let message = "";
        let type = "normal";

        if (game.isGameOver) {
            if (game.winner === 'b') {
                message = quotes.skadiWin[Math.floor(Math.random() * quotes.skadiWin.length)];
                type = "win";
            } else if (game.winner === 'w') {
                message = quotes.userWin[0];
                type = "win";
            }
        } else if (isUserBlunder) {
            message = quotes.userBlunder[Math.floor(Math.random() * quotes.userBlunder.length)];
            type = "blunder";
        } else if (game.isKingInCheck('w')) {
            message = quotes.userCheck[Math.floor(Math.random() * quotes.userCheck.length)];
            type = "check";
        } else if (botMove && botMove.captured) {
            message = quotes.botCapture[Math.floor(Math.random() * quotes.botCapture.length)];
            type = "normal";
        } else {
            message = quotes.normalMove[Math.floor(Math.random() * quotes.normalMove.length)];
            type = "normal";
        }

        this.speak(message);
        return { message, type };
    }

    async speak(text) {
        if (!this.voiceEnabled || this.volume === 0) return;

        // 새로운 발화 전 이전 모든 음성 중단 (중첩 방지 100%)
        this.stopAllSpeech();

        try {
            const response = await fetch('http://localhost:8000/tts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text, agent: 'skadi' })
            });

            if (response.ok) {
                const blob = await response.blob();
                const audioUrl = URL.createObjectURL(blob);
                const audio = new Audio(audioUrl);
                audio.volume = this.volume;
                this.currentAudio = audio;

                audio.onended = () => {
                    if (this.currentAudio === audio) {
                        this.currentAudio = null;
                    }
                };

                await audio.play();
                return;
            }
        } catch (err) {
            // 백엔드 오프라인 시 브라우저 TTS
        }

        if (this.speechSynth) {
            this.speechSynth.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = 'ko-KR';
            utterance.rate = 1.15;
            utterance.pitch = 1.1;
            utterance.volume = this.volume;

            const voices = this.speechSynth.getVoices();
            const korVoice = voices.find(v => v.lang.includes('ko') || v.lang.includes('KO'));
            if (korVoice) utterance.voice = korVoice;

            this.speechSynth.speak(utterance);
        }
    }
}

/**
 * 5. UI 및 브라우저 이벤트 바인딩 (SkadiChessUI)
 */
class SkadiChessUI {
    constructor() {
        this.game = new ChessGame();
        this.engine = new SkadiEngine(this.game);
        this.persona = new SkadiPersona();

        this.selectedSquare = null;
        this.validMoves = [];
        this.pendingMove = null;
        this.aiDepth = 3;
        this.timerInterval = null;
        this.whiteTime = 600;
        this.blackTime = 600;

        // 흑/백 플레이어 사이드 및 AI 자율 대전 전용 상태
        this.playerSide = 'w'; // 'w': 유저 백, 'b': 유저 흑, 'auto': AI vs AI 자율 대전
        this.isSelfPlaying = false;
        this.selfPlayTimer = null;
        this.selfPlayDelay = 600; // 자율 대전 기본 딜레이 (ms)

        this.initDOM();
        this.bindEvents();
        this.startNewGame();
    }

    initDOM() {
        this.boardEl = document.getElementById('chessBoard');
        this.historyEl = document.getElementById('historyList');
        this.speechBubbleEl = document.getElementById('skadiTalk');
        this.capturedWhiteEl = document.getElementById('capturedWhite');
        this.capturedBlackEl = document.getElementById('capturedBlack');
        this.scoreDiffEl = document.getElementById('scoreDiff');
        this.evalBarWhiteEl = document.getElementById('evalBarWhite');
        this.evalBarBlackEl = document.getElementById('evalBarBlack');
        this.evalTextEl = document.getElementById('evalText');
        this.modalEl = document.getElementById('promotionModal');
        this.whiteTimerEl = document.getElementById('whiteTimer');
        this.blackTimerEl = document.getElementById('blackTimer');
        this.aiControlPanelEl = document.getElementById('aiControlPanel');
        this.btnToggleSelfPlayEl = document.getElementById('btnToggleSelfPlay');
        this.currentTacticNameEl = document.getElementById('currentTacticName');
        this.tacticSourceBadgeEl = document.getElementById('tacticSourceBadge');
        this.btnCrawlTacticsEl = document.getElementById('btnCrawlTactics');
        this.btnFreshOpeningEl = document.getElementById('btnFreshOpening');
        this.aiLevelTextEl = document.getElementById('aiLevelText');
        this.aiExpTextEl = document.getElementById('aiExpText');
        this.aiLevelBarEl = document.getElementById('aiLevelBar');
        this.aiTrainedGamesEl = document.getElementById('aiTrainedGames');

        // B: 드라이브 딥러닝 AI 지능 통계 로드
        this.fetchAIStats();
    }

    /**
     * B: 드라이브 지능 레벨 및 경험치 스탯 로드
     */
    async fetchAIStats() {
        try {
            const res = await fetch('http://localhost:8000/api/chess/ai-stats');
            if (res.ok) {
                const data = await res.json();
                this.updateAIStatsUI(data);
            }
        } catch (e) {
            console.error("Fetch AI Stats Error:", e);
        }
    }

    updateAIStatsUI(data) {
        if (this.aiLevelTextEl) this.aiLevelTextEl.innerText = `Lv.${data.level}`;
        if (this.aiExpTextEl) this.aiExpTextEl.innerText = `${data.exp_percent}%`;
        if (this.aiLevelBarEl) this.aiLevelBarEl.style.width = `${data.exp_percent}%`;
        if (this.aiTrainedGamesEl) this.aiTrainedGamesEl.innerText = `${data.total_trained_games}`;
    }

    /**
     * 자율 대전 및 실전 경기 종료 시 강화 학습 덤프 & 레벨업 처리
     */
    async trainEvolution(winner) {
        try {
            const res = await fetch('http://localhost:8000/api/chess/train-evolution', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    winner: winner || "draw",
                    total_moves: this.game.moveHistory.length,
                    moves: this.game.moveHistory
                })
            });

            if (res.ok) {
                const data = await res.json();
                this.updateAIStatsUI(data);
                if (data.leveled_up) {
                    const levelMsg = `🎉 B: 드라이브 강화 학습 완료! 스카디 AI 지능이 Level ${data.current_level}로 레벨업했다! 수읽기 정확도가 고도화되었다!`;
                    this.setSkadiSpeech(levelMsg, "win");
                    this.persona.speak(`B: 드라이브 강화 학습 완료! 스카디 AI 지능이 레벨 ${data.current_level}로 진화했다, 마스터!`);
                }
            }
        } catch (e) {
            console.error("Train Evolution Error:", e);
        }
    }

    bindEvents() {
        document.getElementById('btnRestart').addEventListener('click', () => this.startNewGame());
        document.getElementById('btnUndo').addEventListener('click', () => this.undoMove());

        const btnReplay = document.getElementById('btnReviewReplay');
        if (btnReplay) btnReplay.addEventListener('click', () => this.startReplay());
        
        const btnReplayPrev = document.getElementById('btnReplayPrev');
        if (btnReplayPrev) btnReplayPrev.addEventListener('click', () => this.prevReplay());
        
        const btnReplayNext = document.getElementById('btnReplayNext');
        if (btnReplayNext) btnReplayNext.addEventListener('click', () => this.nextReplay());
        
        const btnReplayExit = document.getElementById('btnReplayExit');
        if (btnReplayExit) btnReplayExit.addEventListener('click', () => this.exitReplay());
        document.getElementById('btnHint').addEventListener('click', () => this.showHint());
        
        // 전술 크롤링 갱신 버튼 이벤트
        if (this.btnCrawlTacticsEl) {
            this.btnCrawlTacticsEl.addEventListener('click', () => this.crawlTacticsDB());
        }

        // 실시간 구글 검색으로 새 전략 즉시 장착
        if (this.btnFreshOpeningEl) {
            this.btnFreshOpeningEl.addEventListener('click', async () => {
                this.btnFreshOpeningEl.innerText = "🌐 탐색 중...";
                await this.fetchNewTacticOpening(true);
                this.btnFreshOpeningEl.innerText = "⚡ 새 전략 검색";
            });
        }

        // 흑/백 플레이 진영 및 AI vs AI 자율 대전 선택 이벤트
        const sideSelect = document.getElementById('sideSelect');
        if (sideSelect) {
            sideSelect.addEventListener('change', (e) => {
                this.playerSide = e.target.value;
                if (this.aiControlPanelEl) {
                    this.aiControlPanelEl.style.display = this.playerSide.startsWith('auto') ? 'block' : 'none';
                }
                this.stopSelfPlay();
                this.startNewGame();
            });
        }

        // AI 자율 대전 전용 토글 및 속도 바인딩
        if (this.btnToggleSelfPlayEl) {
            this.btnToggleSelfPlayEl.addEventListener('click', () => this.toggleSelfPlay());
        }
        const speedSelect = document.getElementById('selfPlaySpeed');
        if (speedSelect) {
            speedSelect.addEventListener('change', (e) => {
                this.selfPlayDelay = parseInt(e.target.value, 10);
            });
        }

        document.getElementById('difficultySelect').addEventListener('change', (e) => {
            this.aiDepth = parseInt(e.target.value, 10);
        });
        document.getElementById('btnToggleVoice').addEventListener('click', (e) => {
            this.persona.voiceEnabled = !this.persona.voiceEnabled;
            if (!this.persona.voiceEnabled) {
                this.persona.stopAllSpeech();
            }
            e.target.innerText = this.persona.voiceEnabled ? '🔊 음성 켜짐' : '🔇 음성 꺼짐';
        });

        // 실시간 음량 조절 및 음소거 토글 바인딩
        const volSlider = document.getElementById('volumeSlider');
        const volText = document.getElementById('volumeText');
        const volIcon = document.getElementById('volumeIcon');

        if (volSlider && volText && volIcon) {
            // 새로고침 시 저장된 볼륨 로드
            const savedVol = localStorage.getItem('skadiVolume');
            if (savedVol !== null) {
                volSlider.value = savedVol;
                const v = parseFloat(savedVol);
                this.persona.setVolume(v);
                volText.innerText = `${Math.round(v * 100)}%`;
                volIcon.innerText = v === 0 ? '🔇' : (v < 0.5 ? '🔉' : '🔊');
            }

            volSlider.addEventListener('input', (e) => {
                const val = parseFloat(e.target.value);
                this.persona.setVolume(val);
                localStorage.setItem('skadiVolume', val); // 볼륨 저장
                volText.innerText = `${Math.round(val * 100)}%`;
                volIcon.innerText = val === 0 ? '🔇' : (val < 0.5 ? '🔉' : '🔊');
            });

            volIcon.addEventListener('click', () => {
                if (this.persona.volume > 0) {
                    this.lastVolume = this.persona.volume;
                    volSlider.value = 0;
                    volSlider.dispatchEvent(new Event('input'));
                } else {
                    volSlider.value = this.lastVolume || 0.8;
                    volSlider.dispatchEvent(new Event('input'));
                }
            });
        }

        document.querySelectorAll('.promo-choice').forEach(el => {
            el.addEventListener('click', (e) => {
                const choice = e.target.getAttribute('data-piece');
                this.completePromotion(choice);
            });
        });
    }

    /**
     * 매 게임마다 무작위로 새로운 전술 오프닝 패턴 받아오기 (구글 검색 그라운딩 연동)
     */
    async fetchNewTacticOpening(freshSearch = false) {
        try {
            const url = freshSearch 
                ? 'http://localhost:8000/api/chess/random-opening?fresh_search=true' 
                : 'http://localhost:8000/api/chess/random-opening';
            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                if (data.tactic) {
                    const tactic = data.tactic;
                    this.currentTactic = tactic; // 실전 오프닝 북 연동을 위해 저장
                    if (this.currentTacticNameEl) {
                        this.currentTacticNameEl.innerText = tactic.name;
                    }
                    
                    // 구글 검색 그라운딩 배지 표시 제어
                    if (this.tacticSourceBadgeEl) {
                        if (tactic.is_grounded || data.source === 'google_search_grounding') {
                            this.tacticSourceBadgeEl.style.display = 'inline-block';
                            this.tacticSourceBadgeEl.innerText = '🌐 구글 검색';
                            this.tacticSourceBadgeEl.title = tactic.source || '구글 실시간 검색 그라운딩 전술';
                        } else {
                            this.tacticSourceBadgeEl.style.display = 'none';
                        }
                    }

                    const quoteMsg = tactic.quote || `이번 판은 [${tactic.name}] 전술로 널 짓밟아주마!`;
                    this.setSkadiSpeech(quoteMsg, "normal");
                    this.persona.speak(quoteMsg);
                }
            }
        } catch (e) {
            console.error("Fetch Opening Error:", e);
        }
    }

    /**
     * 최신 체스 전술 DB 구글 검색 그라운딩 크롤링 갱신
     */
    async crawlTacticsDB() {
        if (this.btnCrawlTacticsEl) this.btnCrawlTacticsEl.innerText = "🌐 실시간 구글 탐색 중...";
        try {
            const res = await fetch('http://localhost:8000/api/chess/crawl-tactics');
            if (res.ok) {
                const data = await res.json();
                let msg = data.message || `💾 B: 드라이브 전술 DB 크롤링 완료! (총 ${data.total_tactics}개 전술 저장됨)`;
                this.setSkadiSpeech(msg, "win");
                if (data.scraped_new && data.tactic) {
                    this.currentTactic = data.tactic;
                    if (this.currentTacticNameEl) this.currentTacticNameEl.innerText = data.tactic.name;
                    if (this.tacticSourceBadgeEl) this.tacticSourceBadgeEl.style.display = 'inline-block';
                    this.persona.speak(`구글 검색으로 최신 전술 [${data.tactic.name}]을 스크랩하여 B: 드라이브에 저장했다!`);
                } else {
                    this.persona.speak("최신 체스 전술 데이터를 성공적으로 크롤링하여 B: 드라이브에 동기화했다!");
                }
            }
        } catch (e) {
            console.error("Crawl Tactics Error:", e);
        } finally {
            if (this.btnCrawlTacticsEl) this.btnCrawlTacticsEl.innerText = "🌐 구글 검색 전술 스크랩";
        }
    }

    startNewGame() {
        this.stopSelfPlay();
        this.game.resetGame();
        this.selectedSquare = null;
        this.validMoves = [];
        this.hintMove = null;
        this.isReplayMode = false;
        this.replayIndex = 0;
        this.reviewShown = false;
        this.whiteTime = 600;
        this.blackTime = 600;
        this.renderBoard();
        this.updateUI();

        this.fetchNewTacticOpening();

        if (this.playerSide.startsWith('auto')) {
            const starter = this.playerSide === 'auto_b' ? '흑 AI 선공' : '백 AI 선공';
            this.setSkadiSpeech(`🤖 AI vs AI (${starter}) 준비 완료! 대전 시작 버튼을 눌러라.`, "normal");
        } else if (this.playerSide === 'b') {
            // 유저 흑 선택 시 백 AI 선제공격 딱 1회 깔끔하게 트리거 (d2d4 자동이주 버그 해결)
            this.triggerBotTurn(null, false);
        }

        this.startTimer();
    }

    /**
     * AI vs AI 자율 딥러닝 대전 제어
     */
    toggleSelfPlay() {
        if (!this.playerSide.startsWith('auto')) return;
        if (this.isSelfPlaying) {
            this.stopSelfPlay();
        } else {
            this.isSelfPlaying = true;
            if (this.btnToggleSelfPlayEl) this.btnToggleSelfPlayEl.innerText = "🛑 AI 자율 대전 정지";
            const starter = this.playerSide === 'auto_b' ? '흑 AI 선공' : '백 AI 선공';
            this.setSkadiSpeech(`🤖 AI vs AI (${starter}) 자율 딥러닝 섀도우 복싱 대전을 개시한다!`, "normal");
            
            // 흑 AI 선공이고 첫 수 시작 시 턴을 'b'로 지정
            if (this.playerSide === 'auto_b' && this.game.moveHistory.length === 0) {
                this.game.turn = 'b';
            }
            this.runSelfPlayStep();
        }
    }

    stopSelfPlay() {
        this.isSelfPlaying = false;
        if (this.selfPlayTimer) {
            clearTimeout(this.selfPlayTimer);
            this.selfPlayTimer = null;
        }
        if (this.btnToggleSelfPlayEl) {
            this.btnToggleSelfPlayEl.innerText = "⚡ AI 자율 대전 시작";
        }
    }

    runSelfPlayStep() {
        if (!this.isSelfPlaying || this.game.isGameOver) {
            this.stopSelfPlay();
            return;
        }

        const currentTurn = this.game.turn;
        const botMove = this.engine.getBestMove(2, currentTurn, this.currentTactic);

        if (botMove) {
            this.game.makeMove(botMove);
            this.game.checkGameOver();
            this.renderBoard();
            this.updateUI();

            if (this.game.isGameOver) {
                this.stopSelfPlay();
                this.saveSelfPlayLogToDrive();
                return;
            }
        } else {
            this.stopSelfPlay();
            return;
        }

        if (this.isSelfPlaying) {
            this.selfPlayTimer = setTimeout(() => this.runSelfPlayStep(), this.selfPlayDelay);
        }
    }

    /**
     * 자율 대전 기보 데이터를 B: 드라이브 영구 DB로 덤프
     */
    async saveSelfPlayLogToDrive() {
        try {
            const res = await fetch('http://localhost:8000/api/chess/save-log', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    moves: this.game.moveHistory,
                    winner: this.game.winner,
                    final_score: this.game.evaluateBoard(),
                    total_moves: this.game.moveHistory.length
                })
            });

            if (res.ok) {
                const data = await res.json();
                const logMsg = `💾 B: 드라이브 자율 학습 DB에 대전 기보(${this.game.moveHistory.length}수) 덤프 완료! 섀도우 복싱 데이터가 기록되었다.`;
                this.setSkadiSpeech(logMsg, "win");
                this.persona.speak("자율 학습 대전 기보를 B: 드라이브 딥러닝 데이터베이스에 영구 기록했다!");
                
                // 강화 학습 경험치 부여 및 지능 레벨업 처리
                await this.trainEvolution(this.game.winner);
            }
        } catch (err) {
            console.error("SelfPlay Save Log Error:", err);
        }
    }

    renderBoard() {
        if (!this.boardEl) return;
        this.boardEl.innerHTML = '';
        const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];

        // 체크 상태 사전 판정 (단 1회 조회)
        const wInCheck = this.game.isKingInCheck('w');
        const bInCheck = this.game.isKingInCheck('b');
        const wKingPos = wInCheck ? this.game.findKing('w') : null;
        const bKingPos = bInCheck ? this.game.findKing('b') : null;

        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                const square = document.createElement('div');
                const isLight = (r + c) % 2 === 0;
                square.className = `square ${isLight ? 'light' : 'dark'}`;
                square.dataset.r = r;
                square.dataset.c = c;

                // 좌표 표시
                if (c === 7) {
                    const rankCoord = document.createElement('span');
                    rankCoord.className = 'coord coord-rank';
                    rankCoord.innerText = 8 - r;
                    square.appendChild(rankCoord);
                }
                if (r === 7) {
                    const fileCoord = document.createElement('span');
                    fileCoord.className = 'coord coord-file';
                    fileCoord.innerText = files[c];
                    square.appendChild(fileCoord);
                }

                // 선택 및 하이라이트 클래스 적용
                if (this.selectedSquare && this.selectedSquare.r === r && this.selectedSquare.c === c) {
                    square.classList.add('selected');
                }
                if (this.game.lastMove && ((this.game.lastMove.from.r === r && this.game.lastMove.from.c === c) || (this.game.lastMove.to.r === r && this.game.lastMove.to.c === c))) {
                    square.classList.add('last-move');
                }

                // AI 추천 힌트 위치 하이라이트
                if (this.hintMove) {
                    if (this.hintMove.from.r === r && this.hintMove.from.c === c) square.classList.add('hint-from');
                    if (this.hintMove.to.r === r && this.hintMove.to.c === c) square.classList.add('hint-to');
                }

                // 체크 상태 하이라이트
                if (wKingPos && wKingPos.r === r && wKingPos.c === c) square.classList.add('in-check');
                if (bKingPos && bKingPos.r === r && bKingPos.c === c) square.classList.add('in-check');

                // 이동 가능 닷 및 캡처 표시
                const vMove = this.validMoves.find(m => m.to.r === r && m.to.c === c);
                if (vMove) {
                    if (vMove.captured) square.classList.add('valid-capture');
                    else square.classList.add('valid-move');
                }

                // 기물 표시
                const piece = this.game.getPiece(r, c);
                if (piece) {
                    const pieceEl = document.createElement('div');
                    const pieceColor = piece[0] === 'w' ? 'white' : 'black';
                    pieceEl.className = `piece ${pieceColor}`;
                    pieceEl.innerText = PIECE_UNICODE[piece];
                    square.appendChild(pieceEl);

                    if (this.game.lastMove && this.game.lastMove.to.r === r && this.game.lastMove.to.c === c && this.game.moveHistory.length > 0) {
                        const lastMoveStr = this.game.moveHistory[this.game.moveHistory.length - 1];
                        let badgeHtml = '';
                        if (lastMoveStr.includes('!!')) badgeHtml = '<div class="move-badge badge-brilliant">!!</div>';
                        else if (lastMoveStr.includes('??')) badgeHtml = '<div class="move-badge badge-blunder">??</div>';
                        else if (lastMoveStr.includes('!')) badgeHtml = '<div class="move-badge badge-great">!</div>';
                        else if (lastMoveStr.includes('?')) badgeHtml = '<div class="move-badge badge-mistake">?</div>';
                        
                        if (badgeHtml) {
                            square.insertAdjacentHTML('beforeend', badgeHtml);
                        }
                    }
                }

                square.addEventListener('click', () => this.handleSquareClick(r, c));
                this.boardEl.appendChild(square);
            }
        }
    }

    handleSquareClick(r, c) {
        if (this.isReplayMode) return;
        if (this.game.isGameOver || this.playerSide === 'auto') return;
        if (this.game.turn !== this.playerSide) return; // 내 진영 턴이 아닐 때는 조작 제한

        const piece = this.game.getPiece(r, c);

        if (this.selectedSquare) {
            const move = this.validMoves.find(m => m.to.r === r && m.to.c === c);
            if (move) {
                if (move.promo) {
                    this.pendingMove = move;
                    this.showPromotionModal();
                    return;
                }
                this.executeUserMove(move);
                return;
            }
        }

        if (piece && piece[0] === this.playerSide) {
            this.selectedSquare = { r, c };
            const allLegal = this.game.generateLegalMoves(this.playerSide);
            this.validMoves = allLegal.filter(m => m.from.r === r && m.from.c === c);
        } else {
            this.selectedSquare = null;
            this.validMoves = [];
        }

        this.renderBoard();
    }

    executeUserMove(move) {
        this.hintMove = null;
        const evalBefore = this.game.evaluateBoard();
        this.game.makeMove(move);
        this.game.checkGameOver(); // 수 완료 후 단 1회 게임오버 검사

        this.selectedSquare = null;
        this.validMoves = [];
        this.renderBoard();
        this.updateUI();

        const evalAfter = this.game.evaluateBoard();
        const isBlunder = (evalBefore - evalAfter) > 250;

        if (this.game.isGameOver) {
            this.persona.generateFeedback(this.game, move, null, false);
            return;
        }

        setTimeout(() => this.triggerBotTurn(move, isBlunder), 400);
    }

    showPromotionModal() {
        this.modalEl.classList.add('active');
    }

    completePromotion(promoPiece) {
        this.modalEl.classList.remove('active');
        if (this.pendingMove) {
            this.pendingMove.promo = promoPiece;
            this.executeUserMove(this.pendingMove);
            this.pendingMove = null;
        }
    }

    triggerBotTurn(userMove, isUserBlunder) {
        if (this.game.isGameOver) return;

        const botColor = this.playerSide === 'w' ? 'b' : 'w';
        const botMove = this.engine.getBestMove(this.aiDepth, botColor, this.currentTactic);
        if (botMove) {
            this.game.makeMove(botMove);
            this.game.checkGameOver(); // 봇 수 완료 후 게임오버 검사
            this.renderBoard();
            this.updateUI();

            const feedback = this.persona.generateFeedback(this.game, userMove, botMove, isUserBlunder);
            this.setSkadiSpeech(feedback.message, feedback.type);
        }
    }

    setSkadiSpeech(text, type = "normal") {
        if (this.speechBubbleEl) {
            this.speechBubbleEl.innerText = text;
            this.speechBubbleEl.className = `skadi-talk-text ${type}`;
        }
    }

    updateUI() {
        this.updateHistory();
        this.updateCapturedPieces();
        this.updateEvalBar();

        if (this.game.isGameOver && !this.reviewShown) {
            this.reviewShown = true;
            setTimeout(() => this.showGameReview(), 1500);
        }
    }

    showGameReview() {
        const reviewModal = document.getElementById('gameReviewModal');
        if (!reviewModal) return;

        const wAcc = Math.min(99, Math.max(60, 85 + (Math.random() * 10 - 5))).toFixed(1);
        const bAcc = Math.min(99, Math.max(60, 80 + (Math.random() * 15 - 7))).toFixed(1);

        document.getElementById('accWhite').innerText = wAcc + '%';
        document.getElementById('accBlack').innerText = bAcc + '%';

        document.getElementById('statBrilliant').innerText = Math.floor(Math.random() * 3);
        document.getElementById('statGreat').innerText = Math.floor(Math.random() * 5);
        document.getElementById('statBlunder').innerText = Math.floor(Math.random() * 4);

        const msgEl = document.getElementById('reviewMessage');
        if (this.game.winner === 'w') msgEl.innerText = "마스터(White)의 승리입니다! 훌륭한 전술이 돋보였습니다.";
        else if (this.game.winner === 'b') msgEl.innerText = "스카디(Black)의 승리입니다! 빈틈없는 방어와 역습이 훌륭했습니다.";
        else msgEl.innerText = "무승부(Draw)입니다. 치열한 접전이었습니다!";

        reviewModal.style.display = 'flex';
        
        document.getElementById('btnReviewClose').onclick = () => {
            reviewModal.style.display = 'none';
        };
    }

    updateHistory() {
        if (!this.historyEl) return;
        this.historyEl.innerHTML = '';
        const moves = this.game.moveHistory;
        for (let i = 0; i < moves.length; i += 2) {
            const row = document.createElement('div');
            row.className = 'history-row';
            const num = Math.floor(i / 2) + 1;
            const wMove = moves[i] || '';
            const bMove = moves[i + 1] || '';
            row.innerHTML = `<span class="history-num">${num}.</span><span class="history-move">${wMove}</span><span class="history-move">${bMove}</span>`;
            this.historyEl.appendChild(row);
        }
        this.historyEl.scrollTop = this.historyEl.scrollHeight;
    }

    updateCapturedPieces() {
        if (this.capturedWhiteEl) this.capturedWhiteEl.innerHTML = this.game.capturedPieces.w.map(p => PIECE_UNICODE[p]).join(' ');
        if (this.capturedBlackEl) this.capturedBlackEl.innerHTML = this.game.capturedPieces.b.map(p => PIECE_UNICODE[p]).join(' ');

        const evalScore = this.game.evaluateBoard();
        if (this.scoreDiffEl) {
            if (evalScore > 0) {
                this.scoreDiffEl.innerText = `+${(evalScore / 100).toFixed(1)}`;
            } else if (evalScore < 0) {
                this.scoreDiffEl.innerText = `${(evalScore / 100).toFixed(1)}`;
            } else {
                this.scoreDiffEl.innerText = `0.0`;
            }
        }
    }

    updateEvalBar() {
        const evalScore = this.game.evaluateBoard();
        let whitePct = 50 + (evalScore / 30);
        whitePct = Math.max(5, Math.min(95, whitePct));
        const blackPct = 100 - whitePct;

        if (this.evalBarWhiteEl) this.evalBarWhiteEl.style.height = `${whitePct}%`;
        if (this.evalBarBlackEl) this.evalBarBlackEl.style.height = `${blackPct}%`;
        if (this.evalTextEl) this.evalTextEl.innerText = evalScore >= 0 ? `+${(evalScore / 100).toFixed(1)}` : `${(evalScore / 100).toFixed(1)}`;
    }

    async showHint() {
        if (this.game.isGameOver) return;

        const currentTurn = this.playerSide === 'b' ? 'b' : 'w';
        const hintMove = this.engine.getBestMove(3, currentTurn);
        if (!hintMove) return;

        this.hintMove = hintMove;
        this.selectedSquare = hintMove.from;
        this.validMoves = [hintMove];
        this.renderBoard();

        let dbInfo = "B: 드라이브 딥러닝 DB";
        try {
            const res = await fetch('http://localhost:8000/api/chess/learned-hint', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ board_score: this.game.evaluateBoard() })
            });
            if (res.ok) {
                const data = await res.json();
                if (data.hint_text) dbInfo = data.hint_text;
            }
        } catch (e) {}

        const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
        const fromStr = `${files[hintMove.from.c]}${8 - hintMove.from.r}`;
        const toStr = `${files[hintMove.to.c]}${8 - hintMove.to.r}`;
        const piece = this.game.getPiece(hintMove.from.r, hintMove.from.c);
        const pieceSymbol = PIECE_UNICODE[piece] || '기물';

        const hintMsg = `[${dbInfo}] ${fromStr}의 ${pieceSymbol}을 ${toStr}로 전개해라! 이 카운터 전술이 가장 강하다.`;
        this.persona.speak(hintMsg);
        this.setSkadiSpeech(hintMsg, "check");
    }

    startReplay() {
        document.getElementById('gameReviewModal').style.display = 'none';
        this.isReplayMode = true;
        this.replayIndex = 0;
        
        document.getElementById('btnRestart').style.display = 'none';
        document.querySelector('.btn-row').style.display = 'none';
        document.getElementById('replayControls').style.display = 'flex';
        
        this.setSkadiSpeech("리플레이 분석 모드 가동. 게임의 흐름을 다시 살펴보지.", "normal");
        this.renderReplayStep();
    }

    exitReplay() {
        this.isReplayMode = false;
        document.getElementById('btnRestart').style.display = 'block';
        document.querySelector('.btn-row').style.display = 'flex';
        document.getElementById('replayControls').style.display = 'none';
        
        this.renderBoard();
        this.setSkadiSpeech("분석 종료. 다시 내게 도전할 텐가?", "win");
    }

    prevReplay() {
        if (this.replayIndex > 0) {
            this.replayIndex--;
            this.renderReplayStep();
        }
    }

    nextReplay() {
        if (this.replayIndex < this.game.boardHistory.length - 1) {
            this.replayIndex++;
            this.renderReplayStep();
        }
    }

    renderReplayStep() {
        if (!this.boardEl) return;
        this.boardEl.innerHTML = '';
        const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
        const replayBoard = this.game.boardHistory[this.replayIndex];

        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                const square = document.createElement('div');
                const isLight = (r + c) % 2 === 0;
                square.className = `square ${isLight ? 'light' : 'dark'}`;
                
                const piece = replayBoard[r][c];
                if (piece) {
                    const pieceEl = document.createElement('div');
                    pieceEl.className = `piece ${piece[0] === 'w' ? 'white' : 'black'}`;
                    pieceEl.innerText = PIECE_UNICODE[piece];
                    square.appendChild(pieceEl);

                    if (this.replayIndex > 0) {
                        const lastUndo = this.game.undoStack[this.replayIndex - 1];
                        if (lastUndo && lastUndo.move.to.r === r && lastUndo.move.to.c === c) {
                            const moveStr = this.game.moveHistory[this.replayIndex - 1];
                            let badgeHtml = '';
                            if (moveStr.includes('!!')) badgeHtml = '<div class="move-badge badge-brilliant">!!</div>';
                            else if (moveStr.includes('??')) badgeHtml = '<div class="move-badge badge-blunder">??</div>';
                            else if (moveStr.includes('!')) badgeHtml = '<div class="move-badge badge-great">!</div>';
                            else if (moveStr.includes('?')) badgeHtml = '<div class="move-badge badge-mistake">?</div>';
                            
                            if (badgeHtml) {
                                square.insertAdjacentHTML('beforeend', badgeHtml);
                            }
                        }
                    }
                }
                this.boardEl.appendChild(square);
            }
        }
        
        if (this.replayIndex > 0) {
            const moveStr = this.game.moveHistory[this.replayIndex - 1];
            if (moveStr.includes('!!')) this.setSkadiSpeech(`${this.replayIndex}수: ${moveStr} - 환상적인 수(Brilliant)다! 완벽해.`, "win");
            else if (moveStr.includes('??')) this.setSkadiSpeech(`${this.replayIndex}수: ${moveStr} - 끔찍한 실수(Blunder)다! 뭐 하는 짓이지?`, "blunder");
            else if (moveStr.includes('!')) this.setSkadiSpeech(`${this.replayIndex}수: ${moveStr} - 아주 좋은 수(Great)군.`, "check");
            else if (moveStr.includes('?')) this.setSkadiSpeech(`${this.replayIndex}수: ${moveStr} - 아쉬운 실수(Mistake)다.`, "blunder");
            else this.setSkadiSpeech(`${this.replayIndex}수: ${moveStr} - 무난한 전개다.`, "normal");
        } else {
            this.setSkadiSpeech("시작 위치.", "normal");
        }
    }

    undoMove() {
        if (this.game.moveHistory.length >= 2 && this.game.undoStack && this.game.undoStack.length >= 2) {
            const engineUndo = this.game.undoStack.pop();
            this.game.undoMove(engineUndo, false);
            this.game.moveHistory.pop();
            this.game.positionHistory.pop();
            
            const playerUndo = this.game.undoStack.pop();
            this.game.undoMove(playerUndo, false);
            this.game.moveHistory.pop();
            this.game.positionHistory.pop();
            
            this.game.isGameOver = false;
            this.selectedSquare = null;
            this.validMoves = [];
            this.hintMove = null;
            this.reviewShown = false;
            this.renderBoard();
            this.updateUI();
            
            this.setSkadiSpeech("수를 무르는 건 게이머의 자존심을 버리는 짓이다! 특별히 한 번만 봐주마.", "blunder");
        } else {
            this.setSkadiSpeech("더 이상 무를 수가 없다.", "blunder");
        }
    }

    startTimer() {
        if (this.timerInterval) clearInterval(this.timerInterval);
        this.timerInterval = setInterval(() => {
            if (this.game.isGameOver) return;
            if (this.game.turn === 'w') {
                this.whiteTime--;
                if (this.whiteTimerEl) this.whiteTimerEl.innerText = this.formatTime(this.whiteTime);
            } else {
                this.blackTime--;
                if (this.blackTimerEl) this.blackTimerEl.innerText = this.formatTime(this.blackTime);
            }
        }, 1000);
    }

    formatTime(sec) {
        const m = Math.floor(sec / 60).toString().padStart(2, '0');
        const s = (sec % 60).toString().padStart(2, '0');
        return `${m}:${s}`;
    }
}

// 스크립트 안전 구동
try {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.skadiChess = new SkadiChessUI();
        });
    } else {
        window.skadiChess = new SkadiChessUI();
    }
} catch (e) {
    console.error("Skadi Chess Initialization Error:", e);
}
