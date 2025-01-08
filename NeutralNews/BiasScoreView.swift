//
//  BiasScoreView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/4/25.
//

import SwiftUI

struct BiasScoreView: View {
    let biasScore: Int
    let maxScore = 100
    let dimensions: CGFloat = 10
    
    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                Rectangle()
                    .fill(.secondary)
                    .frame(maxWidth: .infinity)
                    .clipShape(.rect(cornerRadius: dimensions))
                
                Rectangle()
                    .fill(Color.accentColor)
                    .frame(width: calculateWidth(totalWidth: geometry.size.width))
                    .clipShape(.rect(cornerRadius: dimensions))
            }
            .frame(height: dimensions)
        }
        .frame(height: dimensions)
    }
    
    private func calculateWidth(totalWidth: CGFloat) -> CGFloat {
        let percentage = CGFloat(biasScore) / CGFloat(maxScore)
        return totalWidth * percentage
    }
}

#Preview {
    BiasScoreView(biasScore: 30)
        .padding()
}
