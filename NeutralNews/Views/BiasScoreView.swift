//
//  BiasScoreView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/4/25.
//

import SwiftUI

struct BiasScoreView: View {
    var biasScore: Int
    let maxScore = 100
    let dimensions: CGFloat = 17
    
    @State private var showInfo: Bool = false
    
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
    
    private var infoPopover : some View {
        HStack {
            Image(systemName: "\(Int(biasScore/2)).circle")
                .font(.largeTitle)
                .foregroundStyle(.accent, .secondary)
            
            VStack(alignment: .leading, spacing: 6) {
                Text("Nivel de neutralidad")
                    .font(.system(.subheadline, design: .rounded).weight(.semibold))
                    .foregroundStyle(.accent)
                Text("Este valor indica cuán neutral es la noticia.\n0 es muy sesgada y 50 neutral.")
                    .font(.system(.footnote, design: .rounded))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(12)
        .presentationCompactAdaptation(.popover)
    }
}

#Preview {
    BiasScoreView(biasScore: 50)
        .padding()
}
